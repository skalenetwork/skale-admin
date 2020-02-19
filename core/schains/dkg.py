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
    init_dkg_client, broadcast, get_dkg_broadcast_filter, send_complaint, response, send_allright,
    get_dkg_successful_filter, get_dkg_fail_filter, get_dkg_all_data_received_filter,
    get_dkg_complaint_sent_filter, get_dkg_all_complaints_filter,
    generate_bls_key, generate_bls_key_name, generate_poly_name, get_secret_key_share_filepath,
    DkgFailedError
)
from tools.bls.dkg_client import DkgVerificationError
from tools.helper import write_json

logger = logging.getLogger(__name__)

RECEIVE_TIMEOUT = 1800


def init_bls(skale, schain_name, node_id, sgx_key_name, rotation_id=0):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    if not os.path.isfile(secret_key_share_filepath):
        schain_config = generate_skale_schain_config(skale, schain_name, node_id)
        n = len(schain_config["skaleConfig"]["sChain"]["nodes"])
        t = (2 * n + 1) // 3

        dkg_client = init_dkg_client(schain_config, skale, n, t, sgx_key_name)
        group_index_str = str(int(skale.web3.toHex(dkg_client.group_index)[2:], 16))
        poly_name = generate_poly_name(group_index_str, dkg_client.node_id_dkg, rotation_id)

        dkg_broadcast_filter = get_dkg_broadcast_filter(skale, dkg_client.group_index)
        broadcast(dkg_client, poly_name)

        is_received = [False for _ in range(n)]
        is_received[dkg_client.node_id_dkg] = True

        is_correct = [False for _ in range(n)]
        is_correct[dkg_client.node_id_dkg] = True

        start_time = time.time()
        while False in is_received:
            if time.time() - start_time > RECEIVE_TIMEOUT:
                break

            for event in dkg_broadcast_filter.get_events():
                from_node = event["args"]["fromNode"]

                if not is_received[dkg_client.node_ids_contract[from_node]]:
                    is_received[dkg_client.node_ids_contract[from_node]] = True

                    try:
                        dkg_client.receive_from_node(from_node, event)
                        is_correct[dkg_client.node_ids_contract[from_node]] = True
                    except DkgVerificationError:
                        continue

                    logger.info(
                        f'sChain: {schain_name}. Received by {dkg_client.node_id_dkg} from '
                        f'{dkg_client.node_ids_contract[from_node]}'
                    )
            sleep(1)

        dkg_fail_filter = get_dkg_fail_filter(skale, dkg_client.group_index)

        is_complaint_sent = False
        complainted_node_index = -1
        start_time_response = time.time()
        for i in range(n):
            if not is_correct[i] or not is_received[i]:
                send_complaint(dkg_client, i)
                is_complaint_sent = True
                complainted_node_index = i

        if len(dkg_fail_filter.get_events()) > 0:
            raise DkgFailedError(f'sChain: {schain_name}. Dkg failed due to event FailedDKG')

        is_allright_sent_list = [False for _ in range(n)]
        start_time_allright = time.time()
        dkg_all_data_received_filter = get_dkg_all_data_received_filter(skale,
                                                                        dkg_client.group_index)
        dkg_successful_filter = get_dkg_successful_filter(skale, dkg_client.group_index)
        encrypted_bls_key = 0
        bls_key_name = generate_bls_key_name(group_index_str, dkg_client.node_id_dkg, rotation_id)
        if not is_complaint_sent:
            send_allright(dkg_client)
            encrypted_bls_key = generate_bls_key(dkg_client, bls_key_name)
            is_allright_sent_list[dkg_client.node_id_dkg] = True

        logger.info(f'sChain: {schain_name}. Node`s encrypted bls key is: {encrypted_bls_key}')

        if len(dkg_fail_filter.get_events()) > 0:
            raise DkgFailedError(f'sChain: {schain_name}. Dkg failed due to event FailedDKG')

        is_complaint_received = False
        dkg_complaint_sent_filter = get_dkg_complaint_sent_filter(skale,
                                                                  dkg_client.group_index,
                                                                  dkg_client.node_id_contract)
        for event in dkg_complaint_sent_filter.get_events():
            is_complaint_received = True
            response(dkg_client, event["fromNodeIndex"])

        if len(dkg_fail_filter.get_events()) > 0:
            raise DkgFailedError(f'sChain: {schain_name}. Dkg failed due to event FailedDKG')

        dkg_complaint_sent_filter = get_dkg_all_complaints_filter(skale, dkg_client.group_index)
        if len(dkg_complaint_sent_filter.get_events()) == 0:
            while False in is_allright_sent_list:
                if time.time() - start_time_allright > RECEIVE_TIMEOUT:
                    break
                for event in dkg_all_data_received_filter.get_events():
                    is_allright_sent_list[
                        dkg_client.node_ids_contract[event["args"]["nodeIndex"]]
                    ] = True
                sleep(1)

            for i in range(dkg_client.n):
                if not is_allright_sent_list[i]:
                    send_complaint(dkg_client, i)
                    is_complaint_sent = True

        is_complaint_sent = len(dkg_complaint_sent_filter.get_events())
        if is_complaint_sent or is_complaint_received:
            while len(dkg_fail_filter.get_events()) == 0:
                if time.time() - start_time_response > RECEIVE_TIMEOUT:
                    break
                sleep(1)
                continue

            if len(dkg_fail_filter.get_events()) > 0:
                raise DkgFailedError(f'sChain: {schain_name}. Dkg failed due to event FailedDKG')
            else:
                send_complaint(dkg_client, complainted_node_index)

        if True in is_allright_sent_list:
            if len(dkg_successful_filter.get_events()) > 0:
                common_public_key = skale.schains_data.get_groups_public_key(dkg_client.group_index)
                save_dkg_results(
                    common_public_key=common_public_key,
                    public_key=dkg_client.public_key,
                    t=t,
                    n=n,
                    key_share_name=bls_key_name,
                    filepath=secret_key_share_filepath
                )


def save_dkg_results(common_public_key, public_key, t, n, key_share_name, filepath):
    """Save DKG results to the JSON file on disk"""
    results = {
        'common_public_key': common_public_key,
        'public_key': public_key,
        't': t,
        'n': n,
        'key_share_name': key_share_name
    }
    write_json(filepath, results)
