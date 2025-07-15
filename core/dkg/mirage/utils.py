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
import time

from skale.types.dkg import Status

from core.dkg.mirage.client import MirageDKGClient
from core.dkg.structures import DKGStep
from core.dkg.utils import (
    DkgError,
    BroadcastResult,
    BROADCAST_DATA_SEARCH_SLEEP,
    sync_broadcast_data,
)

logger = logging.getLogger(__name__)


def init_dkg_client(node_id, skale, sgx_eth_key_name, committee_id):
    logger.info('Initializing dkg client')
    schain_nodes = skale.dkg.get_participants(committee_id)
    n = len(schain_nodes)
    t = (2 * n + 1) // 3

    node_id_dkg = -1
    public_keys = [0] * n
    node_ids_contract = {}
    node_ids_dkg = {}
    for i, node_id_contract in enumerate(schain_nodes):
        if node_id_contract is None:
            raise DkgError('Initialization failed, node info is empty.')
        if node_id_contract == node_id:
            node_id_dkg = i

        node_ids_contract[node_id_contract] = i
        node_ids_dkg[i] = node_id_contract
        public_keys[i] = skale.nodes.get(node_id_contract).public_key

    logger.info('Nodes in chain: %s', node_ids_dkg)

    if node_id_dkg == -1:
        raise DkgError(f'{node_id} Initialization failed, nodeID not found for schain.')

    logger.info('Node index in group is %d. Node id on contracts - %d', node_id_dkg, node_id)

    logger.info('Creating DKGClient')
    dkg_client = MirageDKGClient(
        node_id_dkg,
        node_id,
        skale,
        t,
        n,
        public_keys,
        node_ids_dkg,
        node_ids_contract,
        sgx_eth_key_name,
        committee_id,
    )

    return dkg_client


def receive_broadcast_data(dkg_client: MirageDKGClient) -> BroadcastResult:
    n = dkg_client.n

    is_received = [False for _ in range(n)]
    is_received[dkg_client.node_id_dkg] = True

    is_correct = [False for _ in range(n)]
    is_correct[dkg_client.node_id_dkg] = True

    start_time = time.time()

    dkg_filter = dkg_client.get_broadcast_filter()
    broadcasts_found = []

    logger.info('Fetching broadcasted data')

    while False in is_received:
        time_gone = max(start_time, get_latest_block_timestamp(dkg_client.skale)) - start_time
        logger.info(f'Has been trying to receive broadcasted data for {time_gone} seconds')
        is_received, is_correct, broadcasts_found = sync_broadcast_data(
            dkg_client, dkg_filter, is_received, is_correct, broadcasts_found
        )
        check_dkg_id_with_exception(dkg_client)

        time.sleep(BROADCAST_DATA_SEARCH_SLEEP)
    return BroadcastResult(correct=is_correct, received=is_received)


def broadcast_and_check_data(dkg_client):
    if not dkg_client.is_node_broadcasted():
        logger.info('Sending broadcast')
        dkg_client.broadcast()
    else:
        logger.info('Broadcast has been already sent')
        dkg_client.last_completed_step = DKGStep.BROADCAST
    broadcast_result = receive_broadcast_data(dkg_client)
    verification_result = check_broadcast_result(dkg_client, broadcast_result)
    dkg_client.last_completed_step = DKGStep.BROADCAST_VERIFICATION
    return verification_result


def check_broadcast_result(dkg_client, broadcast_result):
    for i in range(dkg_client.n):
        if not broadcast_result.received[i]:
            return False
        if not broadcast_result.correct[i]:
            return False
    return True


def send_alright_and_wait_for_others(dkg_client):
    dkg_client.alright()
    while dkg_client.check_round_id() and dkg_client.get_round_status() == Status.ALRIGHT:
        logger.info('Waiting for ALRIGHT stage to be completed')
        time.sleep(BROADCAST_DATA_SEARCH_SLEEP)
    if not dkg_client.check_round_id():
        raise DkgError('DKG round ID mismatch, restarting DKG.')


def get_latest_block_timestamp(skale):
    return skale.web3.eth.get_block('latest')['timestamp']


def check_dkg_id_with_exception(dkg_client: MirageDKGClient):
    """Check if the DKG ID matches the current committee ID."""
    if not dkg_client.check_round_id():
        logger.info('Restarting DKG: round id mismatch.')
        raise DkgError('Restarting DKG: round id mismatch.')
