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

import os
import logging
from time import sleep

from tools.bls.dkg_utils import (
    init_dkg_client, send_complaint, send_alright, get_latest_block_timestamp, DkgError,
    generate_bls_keys, get_secret_key_share_filepath, check_response, check_no_complaints,
    check_failed_dkg, wait_for_fail, broadcast_and_check_data
)
from tools.bls.dkg_client import KeyGenerationError
from tools.helper import write_json

logger = logging.getLogger(__name__)


def init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    try:
        dkg_client = init_dkg_client(node_id, schain_name, skale, sgx_key_name, rotation_id)
    except DkgError as e:
        logger.error(e)
        channel_started_time = skale.dkg.get_channel_started_time(
            skale.schains.name_to_group_id(schain_name)
        )
        wait_for_fail(skale, schain_name, channel_started_time, "broadcast")
        raise

    n = dkg_client.n

    channel_started_time = skale.dkg.get_channel_started_time(dkg_client.group_index)

    broadcast_and_check_data(dkg_client)

    if not dkg_client.is_everyone_broadcasted():
        wait_for_fail(skale, schain_name, channel_started_time, "broadcast")

    check_failed_dkg(skale, schain_name)

    is_alright_sent_list = [False for _ in range(n)]
    if check_no_complaints(dkg_client):
        logger.info(f'sChain {schain_name}: No complaints sent in schain - sending alright ...')
        send_alright(dkg_client)
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
                send_complaint(dkg_client, i, "alright")

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
            send_complaint(dkg_client, complainted_node_index, "response")
            wait_for_fail(skale, schain_name, channel_started_time, "response")

    if False not in is_alright_sent_list:
        logger.info(f'sChain: {schain_name}: Everyone sent alright')
        if skale.dkg.is_last_dkg_successful(dkg_client.group_index):
            try:
                generated_keys_dict = generate_bls_keys(dkg_client)
                return generated_keys_dict
            except Exception as err:
                raise KeyGenerationError(err)


def run_dkg(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    if not os.path.isfile(secret_key_share_filepath):
        dkg_results = init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id)
        save_dkg_results(dkg_results, secret_key_share_filepath)
        return dkg_results
    return None


def save_dkg_results(dkg_results, filepath):
    """Save DKG results to the JSON file on disk"""
    write_json(filepath, dkg_results)
