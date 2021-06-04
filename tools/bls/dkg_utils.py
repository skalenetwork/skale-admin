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

from skale.schain_config.generator import get_nodes_for_schain

from tools.configs import NODE_DATA_PATH
from tools.bls.dkg_client import DKGClient, DkgError, DkgVerificationError, DkgTransactionError
from tools.bls.skale_dkg_broadcast_filter import Filter

from sgx.http import SgxUnreachableError

logger = logging.getLogger(__name__)

UINT_CONSTANT = 2**256 - 1


class DkgFailedError(DkgError):
    pass


def init_dkg_client(node_id, schain_name, skale, sgx_eth_key_name):
    schain_nodes = get_nodes_for_schain(skale, schain_name)
    n = len(schain_nodes)
    t = (2 * n + 1) // 3

    node_id_dkg = -1
    public_keys = [0] * n
    node_ids_contract = dict()
    node_ids_dkg = dict()
    for i, node in enumerate(schain_nodes):
        if not len(node):
            raise DkgError(f'sChain: {schain_name}:'
                           'Initialization failed, node info is empty.')
        if node['id'] == node_id:
            node_id_dkg = i

        node_ids_contract[node["id"]] = i
        node_ids_dkg[i] = node["id"]

        public_keys[i] = node["publicKey"]

    if node_id_dkg == -1:
        raise DkgError(f'sChain: {schain_name}:'
                       'Initialization failed, nodeID not found for schain.')
    dkg_client = DKGClient(
        node_id_dkg, node_id, skale, t, n, schain_name,
        public_keys, node_ids_dkg, node_ids_contract, sgx_eth_key_name
    )

    return dkg_client


def generate_bls_key_name(group_index_str, node_id, dkg_id):
    return (
            "BLS_KEY:SCHAIN_ID:"
            f"{group_index_str}"
            ":NODE_ID:"
            f"{str(node_id)}"
            ":DKG_ID:"
            f"{str(dkg_id)}"
        )


def generate_poly_name(group_index_str, node_id, dkg_id):
    return (
            "POLY:SCHAIN_ID:"
            f"{group_index_str}"
            ":NODE_ID:"
            f"{str(node_id)}"
            ":DKG_ID:"
            f"{str(dkg_id)}"
        )


def broadcast_and_check_data(dkg_client, poly_name):
    logger.info(f'sChain {dkg_client.schain_name}: Sending broadcast')

    n = dkg_client.n
    schain_name = dkg_client.schain_name
    skale = dkg_client.skale

    is_received = [False for _ in range(n)]
    is_received[dkg_client.node_id_dkg] = True

    is_correct = [False for _ in range(n)]
    is_correct[dkg_client.node_id_dkg] = True

    start_time = skale.dkg.get_channel_started_time(dkg_client.group_index)

    try:
        broadcast(dkg_client, poly_name)
    except SgxUnreachableError as e:
        logger.error(e)
        wait_for_fail(dkg_client.skale, schain_name, start_time)

    dkg_filter = Filter(skale, schain_name, n)
    broadcasts_found = []

    while False in is_received:
        time_gone = get_latest_block_timestamp(dkg_client) - start_time
        if time_gone > dkg_client.dkg_timeout:
            break
        logger.info(f'sChain {schain_name}: trying to receive broadcasted data,'
                    f'{dkg_client.dkg_timeout - time_gone} seconds left')

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
                logger.info(f'sChain {schain_name}: receiving from node {from_node}')
            try:
                dkg_client.receive_from_node(from_node, broadcasted_data)
                is_correct[from_node] = True
                broadcasts_found.append(event.nodeIndex)
            except DkgVerificationError as e:
                logger.error(e)
                continue
            except SgxUnreachableError as e:
                logger.error(e)
                wait_for_fail(dkg_client.skale, schain_name, start_time)

            logger.info(
                f'sChain: {schain_name}. Received by {dkg_client.node_id_dkg} from '
                f'{from_node}'
            )

        logger.info(f'sChain {schain_name}: total received {len(broadcasts_found)} broadcasts'
                    f' from nodes {broadcasts_found}')
        sleep(30)

    check_broadcasted_data(dkg_client, is_correct, is_received)


def generate_bls_keys(dkg_client, rotation_id):
    skale = dkg_client.skale
    schain_name = dkg_client.schain_name
    group_index_str = str(int(skale.web3.toHex(dkg_client.group_index)[2:], 16))
    bls_name = generate_bls_key_name(
        group_index_str, dkg_client.node_id_dkg, rotation_id
    )
    encrypted_bls_key = dkg_client.generate_bls_key(bls_name)
    logger.info(f'sChain: {schain_name}. '
                f'Node`s encrypted bls key is: {encrypted_bls_key}')
    bls_public_keys = dkg_client.get_bls_public_keys()
    common_public_key = skale.key_storage.get_common_public_key(dkg_client.group_index)
    formated_common_public_key = []
    for coord in common_public_key:
        for elem in coord:
            formated_common_public_key.append(elem)
    return {
        'common_public_key': formated_common_public_key,
        'public_key': dkg_client.public_key,
        'bls_public_keys': bls_public_keys,
        't': dkg_client.t,
        'n': dkg_client.n,
        'key_share_name': bls_name
    }


def broadcast(dkg_client, poly_name):
    try:
        dkg_client.broadcast(poly_name)
    except DkgTransactionError:
        pass


def send_complaint(dkg_client, index, reason=""):
    try:
        channel_started_time = dkg_client.skale.dkg.get_channel_started_time(dkg_client.group_index)
        if dkg_client.send_complaint(index):
            wait_for_fail(dkg_client.skale, dkg_client.schain_name, channel_started_time, reason)
    except DkgTransactionError:
        pass


def report_bad_data(dkg_client, index):
    try:
        channel_started_time = dkg_client.skale.dkg.get_channel_started_time(dkg_client.group_index)
        if dkg_client.send_complaint(index, True):
            wait_for_fail(dkg_client.skale, dkg_client.schain_name,
                          channel_started_time, "correct data")
            logger.info(f'sChain {dkg_client.schain_name}:'
                        'Complainted node did not send a response.'
                        f'Sending complaint once again')
            dkg_client.send_complaint(index)
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


def send_alright(dkg_client):
    try:
        dkg_client.alright()
    except DkgTransactionError as e:
        logger.error(f'sChain {dkg_client.schain_name}:' + str(e))


def check_broadcasted_data(dkg_client, is_correct, is_recieved):
    for i in range(dkg_client.n):
        if not is_recieved[i]:
            send_complaint(dkg_client, i, "broadcast")
            break
        if not is_correct[i]:
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


def get_latest_block_timestamp(dkg_client):
    return dkg_client.skale.web3.eth.getBlock("latest")["timestamp"]


def get_secret_key_share_filepath(schain_name, rotation_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_name,
                        f'secret_key_{rotation_id}.json')
