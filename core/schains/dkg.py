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
import json
import logging
import time
from time import sleep
import random

from core.schains.helper import get_schain_config_filepath
from tools.configs import NODE_DATA_PATH
from tools.bls.dkg_utils import init_dkg_client, broadcast, get_dkg_broadcast_filter, send_complaint, response, send_allright, get_dkg_successful_filter, get_dkg_fail_filter, get_dkg_all_data_received_filter, get_dkg_bad_guy_filter, get_dkg_complaint_sent_filter, get_schains_data_contract, get_dkg_all_complaints_filter, generate_bls_key
from tools.bls.dkg_client import DkgVerificationError

logger = logging.getLogger(__name__)


class FailedDKG(Exception):
    def __init__(self, msg):
        super().__init__(msg)


def init_bls(web3, skale, schain_name, sgx_key_name):

    secret_key_share_filepath = get_secret_key_share_filepath(schain_name)
    config_filepath = get_schain_config_filepath(schain_name)

    if not os.path.isfile(secret_key_share_filepath):

        with open(config_filepath, 'r') as infile:
            config_file = json.load(infile)

        n = len(config_file["skaleConfig"]["sChain"]["nodes"])
        t = (2 * n + 1) // 3

        dkg_client = init_dkg_client(config_filepath, web3, skale, n, t, sgx_key_name)
        dkg_id = random.randint(0, 2**256)
        poly_name = "POLY:SCHAIN_ID:" + dkg_client.group_index + ":NODE_ID:" + str(dkg_client.node_id_dkg) + ":DKG_ID:" + str(dkg_id)

        dkg_broadcast_filter = get_dkg_broadcast_filter(skale, dkg_client.group_index)
        broadcast(dkg_client, poly_name)

        is_received = [False] * n
        is_received[dkg_client.node_id_dkg] = True

        is_correct = [False] * n
        is_correct[dkg_client.node_id_dkg] = True

        start_time = time.time()
        while False in is_received:
            time_gone = time.time() - start_time
            if time_gone > 600:
                break

            for event in dkg_broadcast_filter.get_all_entries():
                from_node = event["args"]["fromNode"]

                if not is_received[dkg_client.node_ids_contract[from_node]]:
                    is_received[dkg_client.node_ids_contract[from_node]] = True

                    try:
                        dkg_client.RecieveFromNode(from_node, event)
                        is_correct[dkg_client.node_ids_contract[from_node]] = True
                    except DkgVerificationError:
                        continue

                    logger.info(f'Recieved by {dkg_client.node_id_dkg} from {dkg_client.node_ids_contract[from_node]}')
            sleep(1)

        dkg_fail_filter = get_dkg_fail_filter(skale, dkg_client.group_index)

        is_comlaint_sent = False
        complainted_node_index = -1
        start_time_response = time.time()
        for i in range(n):
            if not is_correct[i] or not is_received[i]:
                send_complaint(dkg_client, i)
                dkg_bad_guy_filter = get_dkg_bad_guy_filter(skale)
                is_comlaint_sent = True
                complainted_node_index = i

        if len(dkg_fail_filter.get_all_entries()) > 0:
            raise FailedDKG("failed due to event FailedDKG")

        is_allright_sent_list = [False] * n
        start_time_allright = time.time()
        dkg_all_data_received_filter = get_dkg_all_data_received_filter(skale, dkg_client.group_index)
        dkg_successful_filter = get_dkg_successful_filter(skale, dkg_client.group_index)
        encrypted_bls_key = 0
        bls_key_name = "BLS_KEY:SCHAIN_ID:" + dkg_client.group_index + ":NODE_ID:" + str(dkg_client.node_id_contract) + ":DKG_ID:" + str(dkg_id)
        if not is_comlaint_sent:
            send_allright(dkg_client)
            encrypted_bls_key = generate_bls_key(dkg_client, bls_key_name)
            is_allright_sent_list[dkg_client.node_id_dkg] = True

        logger.info(f'Node`s encrypted bls key  is : {encrypted_bls_key}')

        if len(dkg_fail_filter.get_all_entries()) > 0:
            raise FailedDKG("failed due to event FailedDKG")

        is_complaint_received = False
        dkg_complaint_sent_filter = get_dkg_complaint_sent_filter(skale, dkg_client.group_index, dkg_client.node_id_contract)
        for event in dkg_complaint_sent_filter.get_all_entries():
            is_complaint_received = True
            response(dkg_client, event["fromNodeIndex"])

        if len(dkg_fail_filter.get_all_entries()) > 0:
            raise FailedDKG("failed due to event FailedDKG")

        dkg_complaint_sent_filter = get_dkg_all_complaints_filter(skale, dkg_client.group_index)
        if len(dkg_complaint_sent_filter.get_all_entries()) == 0:
            while False in is_allright_sent_list:
                if time.time() - start_time_allright > 600:
                    break
                for event in dkg_all_data_received_filter.get_all_entries():
                    is_allright_sent_list[dkg_client.node_ids_contract[event["args"]["nodeIndex"]]] = True
                sleep(1)

            for i in range(dkg_client.n):
                if not is_allright_sent_list[i]:
                    send_complaint(dkg_client, i)
                    is_comlaint_sent = True

        is_comlaint_sent = len(dkg_complaint_sent_filter.get_all_entries())
        if is_comlaint_sent or is_complaint_received:
            while len(dkg_fail_filter.get_all_entries()) == 0:
                if time.time() - start_time_response > 600:
                    break
                sleep(1)
                continue

            if len(dkg_fail_filter.get_all_entries()) > 0:
                raise FailedDKG("failed due to event FailedDKG")
            else:
                send_complaint(dkg_client, complainted_node_index)

        if True in is_allright_sent_list:
            if len(dkg_successful_filter.get_all_entries()) > 0:
                schains_data_contract = get_schains_data_contract(web3)
                common_public_key = schains_data_contract.functions.getGroupsPublicKey(dkg_client.group_index).call()

                with open(secret_key_share_filepath, 'w') as outfile:
                    json.dump({"common_public_key :": common_public_key,
                                "public_key :": dkg_client.public_key}, outfile)


def get_secret_key_share_filepath(schain_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_id, 'secret_key.json')
