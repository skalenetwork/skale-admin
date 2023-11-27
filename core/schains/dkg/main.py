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
from dataclasses import dataclass
from time import sleep

from skale.schain_config.generator import get_nodes_for_schain

from core.schains.dkg.status import ComplaintReason, DKGStatus, DKGStep
from core.schains.dkg.utils import (
    init_dkg_client, send_complaint, get_latest_block_timestamp, DkgError,
    DKGKeyGenerationError, generate_bls_keys, check_response, check_no_complaints,
    check_failed_dkg, wait_for_fail, broadcast_and_check_data
)
from tools.helper import write_json

logger = logging.getLogger(__name__)


def get_dkg_client(node_id, schain_name, skale, sgx_key_name, rotation_id):
    dkg_client = None
    try:
        dkg_client = init_dkg_client(node_id, schain_name, skale, sgx_key_name, rotation_id)
    except DkgError as e:
        logger.exception(e)
        channel_started_time = skale.dkg.get_channel_started_time(
            skale.schains.name_to_group_id(schain_name)
        )
        wait_for_fail(skale, schain_name, channel_started_time, "broadcast")
        raise
    if not dkg_client:
        raise DkgError('Dkg client was not inited successfully')
    return dkg_client


def init_bls(dkg_client, node_id, sgx_key_name, rotation_id=0):
    skale, schain_name = dkg_client.skale, dkg_client.schain_name
    n = dkg_client.n

    channel_started_time = skale.dkg.get_channel_started_time(dkg_client.group_index)

    broadcast_and_check_data(dkg_client)

    if not dkg_client.is_everyone_broadcasted():
        wait_for_fail(skale, schain_name, channel_started_time, "broadcast")

    check_failed_dkg(skale, schain_name)

    is_alright_sent_list = [False for _ in range(n)]
    if check_no_complaints(dkg_client):
        logger.info(f'sChain {schain_name}: No complaints sent in schain - sending alright ...')
        if not dkg_client.is_all_data_received(dkg_client.node_id_dkg):
            dkg_client.alright()
        is_alright_sent_list[dkg_client.node_id_dkg] = True

    check_failed_dkg(skale, schain_name)

    check_response(dkg_client)

    start_time_alright = skale.dkg.get_alright_started_time(dkg_client.group_index)
    while False in is_alright_sent_list:
        check_failed_dkg(skale, schain_name)
        if not check_no_complaints(dkg_client):
            break
        if get_latest_block_timestamp(dkg_client.skale) - \
                start_time_alright > dkg_client.dkg_timeout:
            break
        for from_node in range(dkg_client.n):
            if not is_alright_sent_list[from_node]:
                is_alright_sent_list[from_node] = dkg_client.is_all_data_received(from_node)
        sleep(30)

    if check_no_complaints(dkg_client):
        for i in range(dkg_client.n):
            if not is_alright_sent_list[i] and i != dkg_client.node_id_dkg:
                send_complaint(dkg_client, i, reason=ComplaintReason.NO_ALRIGHT)

    check_response(dkg_client)

    if not dkg_client.is_everyone_sent_algright() and check_no_complaints(dkg_client):
        wait_for_fail(skale, schain_name, channel_started_time, "alright")

    if not check_no_complaints(dkg_client):
        check_response(dkg_client)

        complaint_data = skale.dkg.get_complaint_data(dkg_client.group_index)
        complainted_node_index = dkg_client.node_ids_contract[complaint_data[1]]

        wait_for_fail(skale, schain_name, channel_started_time, "correct data")

        complaint_itself = complainted_node_index == dkg_client.node_id_dkg
        if check_failed_dkg(skale, schain_name) and not complaint_itself:
            logger.info(f'sChain: {schain_name}. '
                        'Accused node has not sent response. Sending complaint...')
            send_complaint(dkg_client, complainted_node_index, reason=ComplaintReason.NO_RESPONSE)
            wait_for_fail(skale, schain_name, channel_started_time, "response")

    if False in is_alright_sent_list:
        logger.info(f'sChain: {schain_name}: Not everyone sent alright')
        raise DkgError(f'sChain: {schain_name}: Not everyone sent alright')
    else:
        logger.info(f'sChain: {schain_name}: Everyone sent alright')
        return dkg_client


def is_last_dkg_finished(skale, schain_name):
    schain_index = skale.schains.name_to_group_id(schain_name)
    num_of_nodes = len(get_nodes_for_schain(skale, schain_name))
    return skale.dkg.get_number_of_completed(schain_index) == num_of_nodes


def save_dkg_results(dkg_results, filepath):
    """Save DKG results to the JSON file on disk"""
    write_json(filepath, dkg_results)


@dataclass
class DKGResult:
    status: DKGStatus
    step: DKGStep
    keys_data: dict


def safe_run_dkg(
    skale,
    dkg_client,
    schain_name,
    node_id,
    sgx_key_name,
    rotation_id
) -> DKGResult:
    keys_data, status = None, None
    try:
        if is_last_dkg_finished(skale, schain_name):
            logger.info(f'Dkg for {schain_name} is completed. Fetching data')
            dkg_client.fetch_all_broadcasted_data()
        elif skale.dkg.is_channel_opened(
            skale.schains.name_to_group_id(schain_name)
        ):
            logger.info(f'Starting dkg procedure for {schain_name}')
            if skale.dkg.is_channel_opened(
                skale.schains.name_to_group_id(schain_name)
            ):
                status = DKGStatus.IN_PROGRESS
                init_bls(dkg_client, node_id, sgx_key_name, rotation_id)
            else:
                status = DKGStatus.FAILED
    except DkgError as e:
        logger.info(f'sChain {schain_name} DKG procedure failed with {e}')
        status = DKGStatus.FAILED

    if not dkg_client:
        status = DKGStatus.FAILED

    if status != DKGStatus.FAILED:
        try:
            keys_data = generate_bls_keys(dkg_client)
        except DKGKeyGenerationError as e:
            logger.info(
                f'sChain {schain_name} DKG failed during key generation, err {e}')
            status = DKGStatus.KEY_GENERATION_ERROR

    if keys_data:
        status = DKGStatus.DONE
    else:
        if status != DKGStatus.KEY_GENERATION_ERROR:
            status = DKGStatus.FAILED
    return DKGResult(
        keys_data=keys_data,
        step=dkg_client.last_completed_step,
        status=status
    )
