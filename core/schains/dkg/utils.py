#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
from time import sleep
from typing import NamedTuple

from skale.schain_config.generator import get_nodes_for_schain

from tools.configs import NODE_DATA_PATH
from core.schains.dkg.structures import ComplaintReason, DKGStep
from core.schains.dkg.client import DKGClient, DkgError, DkgVerificationError, DkgTransactionError
from core.schains.dkg.broadcast_filter import Filter

from sgx.http import SgxUnreachableError

logger = logging.getLogger(__name__)

UINT_CONSTANT = 2**256 - 1
BROADCAST_DATA_SEARCH_SLEEP = 30


class DkgFailedError(DkgError):
    pass


class DKGKeyGenerationError(DkgError):
    pass


class BroadcastResult(NamedTuple):
    received: list[bool]
    correct: list[bool]


def init_dkg_client(node_id, schain_name, skale, sgx_eth_key_name, rotation_id):
    logger.info('Initializing dkg client')
    schain_nodes = get_nodes_for_schain(skale, schain_name)
    n = len(schain_nodes)
    t = (2 * n + 1) // 3

    node_id_dkg = -1
    public_keys = [0] * n
    node_ids_contract = {}
    node_ids_dkg = {}
    for i, node in enumerate(schain_nodes):
        if not len(node):
            raise DkgError(f'sChain: {schain_name}: '
                           'Initialization failed, node info is empty.')
        if node['id'] == node_id:
            node_id_dkg = i

        node_ids_contract[node["id"]] = i
        node_ids_dkg[i] = node["id"]
        public_keys[i] = node["publicKey"]

    logger.info('Nodes in chain: %s', node_ids_dkg)

    if node_id_dkg == -1:
        raise DkgError(f'sChain: {schain_name}: {node_id} '
                       'Initialization failed, nodeID not found for schain.')

    logger.info('Node index in group is %d. Node id on contracts - %d', node_id_dkg, node_id)

    logger.info('Creating DKGClient')
    dkg_client = DKGClient(
        node_id_dkg, node_id, skale, t, n, schain_name,
        public_keys, node_ids_dkg, node_ids_contract, sgx_eth_key_name, rotation_id
    )

    return dkg_client


def sync_broadcast_data(dkg_client, dkg_filter, is_received, is_correct, broadcasts_found):
    logger.info(f'sChain {dkg_client.schain_name}: Syncing broadcast data before finishing '
                f'broadcast phase')
    if dkg_client.is_everyone_broadcasted():
        events = dkg_filter.get_events(from_channel_started_block=True)
    else:
        events = dkg_filter.get_events()
    for event in events:
        from_node = dkg_client.node_ids_contract[event.nodeIndex]
        if is_received[from_node] and from_node != dkg_client.node_id_dkg:
            continue
        else:
            is_received[from_node] = True
        broadcasted_data = [event.verificationVector, event.secretKeyContribution]
        is_received[from_node] = True
        if from_node != dkg_client.node_id_dkg:
            logger.info(f'sChain {dkg_client.schain_name}: receiving from node {from_node}')
        try:
            dkg_client.receive_from_node(from_node, broadcasted_data)
            is_correct[from_node] = True
            broadcasts_found.append(event.nodeIndex)
        except DkgVerificationError as e:
            logger.error(e)
            continue
        logger.info(
            f'sChain: {dkg_client.schain_name}. Received by {dkg_client.node_id_dkg} from '
            f'{from_node}'
        )
    logger.info(f'sChain {dkg_client.schain_name}: total received {len(broadcasts_found)} '
                f'broadcasts from nodes {broadcasts_found}')
    return (is_received, is_correct, broadcasts_found)


def receive_broadcast_data(dkg_client: DKGClient) -> BroadcastResult:
    n = dkg_client.n
    schain_name = dkg_client.schain_name
    skale = dkg_client.skale

    is_received = [False for _ in range(n)]
    is_received[dkg_client.node_id_dkg] = True

    is_correct = [False for _ in range(n)]
    is_correct[dkg_client.node_id_dkg] = True

    start_time = skale.dkg.get_channel_started_time(dkg_client.group_index)

    dkg_filter = Filter(skale, schain_name, n)
    broadcasts_found = []

    logger.info('Fetching broadcasted data')

    while False in is_received:
        time_gone = get_latest_block_timestamp(dkg_client.skale) - start_time
        time_left = max(dkg_client.dkg_timeout - time_gone, 0)
        logger.info(f'sChain {schain_name}: trying to receive broadcasted data,'
                    f'{time_left} seconds left')
        is_received, is_correct, broadcasts_found = sync_broadcast_data(dkg_client, dkg_filter,
                                                                        is_received, is_correct,
                                                                        broadcasts_found)
        if time_gone > dkg_client.dkg_timeout:
            break

        sleep(BROADCAST_DATA_SEARCH_SLEEP)
    return BroadcastResult(correct=is_correct, received=is_received)


def broadcast_and_check_data(dkg_client):
    if not dkg_client.is_node_broadcasted():
        logger.info('Sending broadcast')
        dkg_client.broadcast()
    else:
        logger.info('Broadcast has been already sent')
        dkg_client.last_completed_step = DKGStep.BROADCAST
    broadcast_result = receive_broadcast_data(dkg_client)
    check_broadcast_result(dkg_client, broadcast_result)
    dkg_client.last_completed_step = DKGStep.BROADCAST_VERIFICATION


def generate_bls_keys(dkg_client):
    skale = dkg_client.skale
    schain_name = dkg_client.schain_name
    try:
        if not dkg_client.is_bls_key_generated():
            encrypted_bls_key = dkg_client.generate_bls_key()
            logger.info(f'sChain: {schain_name}. '
                        f'Node`s encrypted bls key is: {encrypted_bls_key}')
        else:
            logger.info(f'sChain: {schain_name}. BLS key exists. Fetching')
            dkg_client.fetch_bls_public_key()

        bls_public_keys = dkg_client.get_bls_public_keys()
        common_public_key = skale.key_storage.get_common_public_key(dkg_client.group_index)
        formated_common_public_key = [
            elem
            for coord in common_public_key
            for elem in coord
        ]
    except Exception as err:
        raise DKGKeyGenerationError(err)
    dkg_client.last_completed_step = DKGStep.KEY_GENERATION
    return {
        'common_public_key': formated_common_public_key,
        'public_key': dkg_client.public_key,
        'bls_public_keys': bls_public_keys,
        't': dkg_client.t,
        'n': dkg_client.n,
        'key_share_name': dkg_client.bls_name
    }


def send_complaint(dkg_client: DKGClient, index: int, reason: ComplaintReason):
    channel_started_time = dkg_client.skale.dkg.get_channel_started_time(dkg_client.group_index)
    reason_to_missing = {
        ComplaintReason.NO_ALRIGHT: 'alright',
        ComplaintReason.NO_BROADCAST: 'broadcast',
        ComplaintReason.NO_RESPONSE: 'response'
    }
    missing = reason_to_missing.get(reason, '')
    try:
        if dkg_client.send_complaint(index, reason=reason):
            wait_for_fail(
                dkg_client.skale,
                dkg_client.schain_name,
                channel_started_time,
                missing
            )
    except DkgTransactionError:
        pass


def report_bad_data(dkg_client, index):
    try:
        channel_started_time = dkg_client.skale.dkg.get_channel_started_time(dkg_client.group_index)
        if dkg_client.send_complaint(index, reason=ComplaintReason.BAD_DATA):
            wait_for_fail(dkg_client.skale, dkg_client.schain_name,
                          channel_started_time, "correct data")
            logger.info(f'sChain {dkg_client.schain_name}:'
                        'Complainted node did not send a response.'
                        f'Sending complaint once again')
            dkg_client.send_complaint(index, reason=ComplaintReason.NO_RESPONSE)
            wait_for_fail(dkg_client.skale, dkg_client.schain_name,
                          channel_started_time, "response")
    except DkgTransactionError:
        pass


def response(dkg_client, to_node_index):
    try:
        dkg_client.response(to_node_index)
    except DkgTransactionError as e:
        logger.error(f'sChain {dkg_client.schain_name}:' + str(e))
    except SgxUnreachableError as e:
        logger.error(f'sChain {dkg_client.schain_name}:' + str(e))


def check_broadcast_result(dkg_client, broadcast_result):
    for i in range(dkg_client.n):
        if not broadcast_result.received[i]:
            send_complaint(dkg_client, i, reason=ComplaintReason.NO_BROADCAST)
            break
        if not broadcast_result.correct[i]:
            report_bad_data(dkg_client, i)
            break


def check_failed_dkg(skale, schain_name):
    group_index = skale.schains.name_to_group_id(schain_name)
    if not skale.dkg.is_channel_opened(group_index):
        if not skale.dkg.is_last_dkg_successful(group_index) \
                and skale.dkg.get_time_of_last_successful_dkg(group_index) != 0:
            raise DkgFailedError(f'sChain: {schain_name}. Dkg failed')
    return True


def check_response(dkg_client):
    complaint_data = dkg_client.skale.dkg.get_complaint_data(dkg_client.group_index)
    if complaint_data[0] != complaint_data[1] and complaint_data[1] == dkg_client.node_id_contract:
        logger.info(f'sChain: {dkg_client.schain_name}: Complaint received. Sending response ...')
        channel_started_time = dkg_client.skale.dkg.get_channel_started_time(dkg_client.group_index)
        response(dkg_client, complaint_data[0])
        logger.info(f'sChain: {dkg_client.schain_name}: Response sent.'
                    ' Waiting for FailedDkg event ...')
        wait_for_fail(dkg_client.skale, dkg_client.schain_name, channel_started_time)


def check_no_complaints(dkg_client):
    complaint_data = dkg_client.skale.dkg.get_complaint_data(dkg_client.group_index)
    return complaint_data[0] == UINT_CONSTANT and complaint_data[1] == UINT_CONSTANT


def wait_for_fail(skale, schain_name, channel_started_time, reason=""):
    logger.info(f'sChain: {schain_name}. Will wait for FailedDkg event')
    start_time = get_latest_block_timestamp(skale)
    dkg_timeout = skale.constants_holder.get_dkg_timeout()
    group_index = skale.schains.name_to_group_id(schain_name)
    while get_latest_block_timestamp(skale) - start_time < dkg_timeout:
        if len(reason) > 0:
            logger.info(f'sChain: {schain_name}.'
                        f' Not all nodes sent {reason}. Waiting for FailedDkg event...')
        else:
            logger.info(f'sChain: {schain_name}. Waiting for FailedDkg event...')
        check_failed_dkg(skale, schain_name)
        if channel_started_time != skale.dkg.get_channel_started_time(group_index):
            raise DkgFailedError(
                f'sChain: {schain_name}. Dkg failed due to event FailedDKG'
            )
        sleep(30)


def get_latest_block_timestamp(skale):
    return skale.web3.eth.get_block("latest")["timestamp"]


def get_secret_key_share_filepath(schain_name, rotation_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_name,
                        f'secret_key_{rotation_id}.json')
