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

from skale.schain_config.generator import get_nodes_for_schain
from tools.bls.dkg_utils import (
    init_dkg_client, send_complaint, send_alright, get_latest_block_timestamp,
    generate_bls_key, get_bls_public_keys, generate_bls_key_name, generate_poly_name,
    get_secret_key_share_filepath, is_all_data_received, is_everyone_broadcasted,
    check_response, check_no_complaints, check_failed_dkg, wait_for_fail, broadcast_and_check_data,
    get_complaint_data, get_complaint_started_time, get_alright_started_time,
    get_channel_started_time, RECEIVE_TIMEOUT
)
from tools.helper import write_json

logger = logging.getLogger(__name__)


def init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    schain_nodes = get_nodes_for_schain(skale, schain_name)
    n = len(schain_nodes)
    t = (2 * n + 1) // 3

    dkg_client = init_dkg_client(schain_nodes, node_id, schain_name, skale, n, t, sgx_key_name)
    group_index_str = str(int(skale.web3.toHex(dkg_client.group_index)[2:], 16))
    poly_name = generate_poly_name(group_index_str, dkg_client.node_id_dkg, rotation_id)

    channel_started_time = get_channel_started_time(dkg_client)

    broadcast_and_check_data(dkg_client, poly_name)

    if not is_everyone_broadcasted(dkg_client):
        wait_for_fail(dkg_client, channel_started_time, "broadcast")

    check_failed_dkg(dkg_client)

    is_alright_sent_list = [False for _ in range(n)]
    if check_no_complaints(dkg_client):
        logger.info(f'sChain {schain_name}: No complaints sent in schain - sending alright ...')
        send_alright(dkg_client)
        is_alright_sent_list[dkg_client.node_id_dkg] = True

    check_failed_dkg(dkg_client)

    check_response(dkg_client)

    if check_no_complaints(dkg_client):
        start_time_alright = get_alright_started_time(dkg_client)
        while False in is_alright_sent_list:
            check_failed_dkg(dkg_client)
            if get_latest_block_timestamp(dkg_client) - start_time_alright > RECEIVE_TIMEOUT:
                break
            for from_node in range(dkg_client.n):
                if not is_alright_sent_list[from_node]:
                    is_alright_sent_list[from_node] = is_all_data_received(dkg_client, from_node)
            check_response(dkg_client)
            sleep(30)

        if check_no_complaints(dkg_client):
            for i in range(dkg_client.n):
                if not is_alright_sent_list[i] and i != dkg_client.node_id_dkg:
                    send_complaint(dkg_client, i, "alright")

    check_response(dkg_client)

    if not check_no_complaints(dkg_client):
        check_response(dkg_client)

        complaint_data = get_complaint_data(dkg_client)
        complainted_node_index = dkg_client.node_ids_contract[complaint_data[1]]

        start_time_response = get_complaint_started_time(dkg_client)
        while check_failed_dkg(dkg_client):
            if get_latest_block_timestamp(dkg_client) - start_time_response > RECEIVE_TIMEOUT:
                break
            sleep(30)

        complaint_itself = complainted_node_index == dkg_client.node_id_dkg
        if check_failed_dkg(dkg_client) and not complaint_itself:
            send_complaint(dkg_client, complainted_node_index, "response")

    if False not in is_alright_sent_list:
        logger.info(f'sChain: {schain_name}: Everyone sent alright')
        if skale.dkg.is_last_dkg_successful(dkg_client.group_index):
            bls_name = generate_bls_key_name(group_index_str, dkg_client.node_id_dkg, rotation_id)
            encrypted_bls_key = generate_bls_key(dkg_client, bls_name)
            logger.info(f'sChain: {schain_name}. Node`s encrypted bls key is: {encrypted_bls_key}')
            bls_public_keys = get_bls_public_keys(dkg_client)
            common_public_key = skale.key_storage.get_common_public_key(dkg_client.group_index)
            formated_common_public_key = []
            for coord in common_public_key:
                for elem in coord:
                    formated_common_public_key.append(elem)
            return {
                'common_public_key': formated_common_public_key,
                'public_key': dkg_client.public_key,
                'bls_public_keys': bls_public_keys,
                't': t,
                'n': n,
                'key_share_name': bls_name
            }


def run_dkg(skale, schain_name, node_id, sgx_key_name, rotation_id=0,
            node_data_path=None):
    secret_key_share_filepath = get_secret_key_share_filepath(
        schain_name, rotation_id, node_data_path)
    if not os.path.isfile(secret_key_share_filepath):
        dkg_results = init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id)
        save_dkg_results(dkg_results, secret_key_share_filepath)


def save_dkg_results(dkg_results, filepath):
    """Save DKG results to the JSON file on disk"""
    write_json(filepath, dkg_results)
