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
import time
from time import sleep

from skale.schain_config import generate_skale_schain_config
from tools.bls.dkg_utils import (
    init_dkg_client, broadcast, send_complaint, response, send_alright,
    generate_bls_key, generate_bls_key_name, generate_poly_name, get_secret_key_share_filepath,
    get_broadcasted_data, is_all_data_received, get_complaint_data, is_everyone_broadcasted,
    check_broadcasted_data, check_failed_dkg, get_channel_started_time,
    DkgFailedError
)
from tools.bls.dkg_client import DkgVerificationError
from tools.helper import write_json

logger = logging.getLogger(__name__)

RECEIVE_TIMEOUT = 1800


def init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    schain_config = generate_skale_schain_config(skale, schain_name, node_id)
    n = len(schain_config["skaleConfig"]["sChain"]["nodes"])
    t = (2 * n + 1) // 3

    dkg_client = init_dkg_client(schain_config, skale, n, t, sgx_key_name)
    group_index_str = str(int(skale.web3.toHex(dkg_client.group_index)[2:], 16))
    poly_name = generate_poly_name(group_index_str, dkg_client.node_id_dkg, rotation_id)

    broadcast(dkg_client, poly_name)

    is_received = [False for _ in range(n)]
    is_received[dkg_client.node_id_dkg] = True

    is_correct = [False for _ in range(n)]
    is_correct[dkg_client.node_id_dkg] = True

    start_time = time.time()
    while False in is_received:
        if time.time() - start_time > RECEIVE_TIMEOUT:
            break

        for from_node in range(dkg_client.n):
            if not is_received[from_node]:
                secret_key_contribution, verification_vector = get_broadcasted_data(
                    dkg_client, from_node
                )
                if secret_key_contribution == [] or verification_vector == []:
                    continue
                broadcasted_data = [verification_vector, secret_key_contribution]
                is_received[from_node] = True

                try:
                    dkg_client.receive_from_node(from_node, broadcasted_data)
                    is_correct[from_node] = True
                except DkgVerificationError:
                    continue

                logger.info(
                    f'sChain: {schain_name}. Received by {dkg_client.node_id_dkg} from '
                    f'{from_node}'
                )
        sleep(1)

    is_complaint_sent = False
    complainted_node_index = -1
    start_time_response = time.time()
    is_complaint_sent, complainted_node_index = check_broadcasted_data(
                                        dkg_client, is_correct, is_received
    )
    all_broadcasted = is_everyone_broadcasted(dkg_client)
    if not all_broadcasted:
        channel_started_time = get_channel_started_time(dkg_client)
        while True:
            check_failed_dkg(dkg_client)
            if channel_started_time != get_channel_started_time(dkg_client):
                raise DkgFailedError(
                    f'sChain: {dkg_client.schain_name}. Dkg failed due to event FailedDKG'
                )
            sleep(30)

    check_failed_dkg(dkg_client)

    is_alright_sent_list = [False for _ in range(n)]
    start_time_alright = time.time()
    if not is_complaint_sent:
        send_alright(dkg_client)
        is_alright_sent_list[dkg_client.node_id_dkg] = True

    check_failed_dkg(dkg_client)

    is_complaint_received = False
    complaint_data = get_complaint_data(dkg_client)
    if complaint_data[0] != complaint_data[1] and complaint_data[1] == dkg_client.node_id_contract:
        is_complaint_received = True
        response(dkg_client, complaint_data[0])

    check_failed_dkg(dkg_client)

    pow2 = 2**256 - 1
    complaint_data = get_complaint_data(dkg_client)
    if complaint_data[0] == complaint_data[1] and complaint_data[0] == pow2:
        while False in is_alright_sent_list:
            if time.time() - start_time_alright > RECEIVE_TIMEOUT:
                break
            for from_node in range(dkg_client.n):
                if not is_alright_sent_list[from_node]:
                    is_alright_sent_list[from_node] = is_all_data_received(dkg_client, from_node)
            complaint_data = get_complaint_data(dkg_client)
            if complaint_data[0] != pow2 and complaint_data[1] == dkg_client.node_id_contract:
                is_complaint_received = True
                response(dkg_client, complaint_data[0])
            sleep(1)

        for i in range(dkg_client.n):
            if not is_alright_sent_list[i] and i != dkg_client.node_id_dkg:
                send_complaint(dkg_client, i)
                complainted_node_index = i
                is_complaint_sent = True

    complaint_data = get_complaint_data(dkg_client)
    if complaint_data[0] != pow2 and complaint_data[1] == dkg_client.node_id_contract:
        is_complaint_received = True
        response(dkg_client, complaint_data[0])

    complaint_data = get_complaint_data(dkg_client)
    is_complaint_sent = complaint_data[0] != complaint_data[1]
    if is_complaint_sent or is_complaint_received:
        is_group_failed = not skale.dkg.is_last_dkg_successful(dkg_client.group_index)
        is_channel_opened = dkg_client.is_channel_opened()
        while not is_group_failed or is_channel_opened:
            if time.time() - start_time_response > RECEIVE_TIMEOUT:
                break
            complaint_data = get_complaint_data(dkg_client)
            complainted_node_index = dkg_client.node_ids_contract[complaint_data[1]]
            if complaint_data[0] != pow2 and complaint_data[1] == dkg_client.node_id_contract:
                is_complaint_received = True
                response(dkg_client, complaint_data[0])
            is_group_failed = not skale.dkg.is_last_dkg_successful(dkg_client.group_index)
            is_channel_opened = dkg_client.is_channel_opened()
            sleep(1)

        is_group_opened = dkg_client.is_channel_opened()
        is_group_failed = not skale.dkg.is_last_dkg_successful(dkg_client.group_index)
        complaint_itself = complainted_node_index == dkg_client.node_id_dkg
        if is_group_opened or not is_group_failed and is_complaint_sent and not complaint_itself:
            send_complaint(dkg_client, complainted_node_index)
        raise DkgFailedError(f'sChain: {schain_name}. Dkg failed due to event FailedDKG')

    if False not in is_alright_sent_list:
        if skale.dkg.is_last_dkg_successful(dkg_client.group_index):
            encrypted_bls_key = 0
            bls_name = generate_bls_key_name(group_index_str, dkg_client.node_id_dkg, rotation_id)
            encrypted_bls_key = generate_bls_key(dkg_client, bls_name)
            logger.info(f'sChain: {schain_name}. Node`s encrypted bls key is: {encrypted_bls_key}')
            common_public_key = skale.key_storage.get_common_public_key(dkg_client.group_index)
            formated_common_public_key = []
            for coord in common_public_key:
                for elem in coord:
                    formated_common_public_key.append(elem)
            return {
                'common_public_key': formated_common_public_key,
                'public_key': dkg_client.public_key,
                't': t,
                'n': n,
                'key_share_name': bls_name
            }


def run_dkg(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    if not os.path.isfile(secret_key_share_filepath):
        dkg_results = init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id)
        save_dkg_results(dkg_results, secret_key_share_filepath)


def save_dkg_results(dkg_results, filepath):
    """Save DKG results to the JSON file on disk"""
    write_json(filepath, dkg_results)
