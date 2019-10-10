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
import time
from time import sleep

from core.schains.helper import get_schain_config_filepath
from tools.configs import NODE_DATA_PATH
from tools.bls.dkg_utils import init_dkg_client, broadcast, get_dkg_broadcast_filter, get_dkg_contract, send_complaint, response, send_allright, get_dkg_successful_filter, get_dkg_fail_filter, get_dkg_all_data_received_filter, get_dkg_bad_guy_filter, get_dkg_complaint_sent_filter, get_schains_data_contract, get_dkg_all_complaints_filter
from tools.bls.dkg_client import DkgVerificationError

class FailedDKG(Exception):
    def __init__(self, msg):
        super().__init__(msg)

def init_bls(web3, wallet, schain_name):
    if len(get_dkg_successful_filter(web3, web3.sha3(text = schain_name)).get_all_entries()) > 0:
        print("ALLREADY EXIST")
        # Schain already exists
        return

    secret_key_share_filepath = get_secret_key_share_filepath(schain_name)
    config_filepath = get_schain_config_filepath(schain_name)

    group_index = web3.sha3(text = schain_name)

    if not os.path.isfile(secret_key_share_filepath):

        with open(config_filepath, 'r') as infile:
            config_file = json.load(infile)

        n = len(config_file["skaleConfig"]["sChain"]["nodes"])
        t = (2 * n + 1) // 3  # default value

        dkg_contract = get_dkg_contract(web3)

        local_wallet = wallet.get_full()

        dkg_client = init_dkg_client(config_filepath, web3, local_wallet, n, t)

        dkg_broadcast_filter = get_dkg_broadcast_filter(web3, dkg_client.group_index)
        broadcast(dkg_client, web3)

        is_received = [False] * n
        is_received[dkg_client.node_id] = True

        is_correct = [False] * n
        is_correct[dkg_client.node_id] = True

        start_time = time.time()
        while False in is_received:
            time_gone = time.time() - start_time
            if time_gone > 600:
                break

            print(web3.eth.blockNumber)
            for event in dkg_broadcast_filter.get_all_entries():
                from_node = event["args"]["fromNode"]
                print(event)

                if is_received[dkg_client.node_ids[from_node]] == False:
                    is_received[dkg_client.node_ids[from_node]] = True

                    try:
                        dkg_client.RecieveAll(from_node, event)
                        is_correct[dkg_client.node_ids[from_node]] = True
                    except DkgVerificationError:
                        continue

                    print("Recieved by", dkg_client.node_ids[dkg_client.node_id])
            sleep(1)

        # SEND A COMPLAINT HERE IF NOT ALL DATA WAS RECEIVED OR SOME DATA WAS NOT VERIFIED
        dkg_fail_filter = get_dkg_fail_filter(web3, dkg_client.group_index)

        is_comlaint_sent = False
        complainted_node_index = -1
        start_time_response = time.time()
        for i in range(n):
            if is_correct[i] == False or is_received[i] == False:
                send_complaint(dkg_client, i, web3)
                dkg_bad_guy_filter = get_dkg_bad_guy_filter(web3)
                is_comlaint_sent = True
                complainted_node_index = i

        if len(dkg_fail_filter.get_all_entries()) > 0:
            # TERMINATE DKG
            raise FailedDKG("failed dut tot event FailedDKG")

        is_allright_sent_list = [False] * n
        start_time_allright = time.time()
        dkg_all_data_received_filter = get_dkg_all_data_received_filter(web3, dkg_client.group_index)
        dkg_successful_filter = get_dkg_successful_filter(web3, dkg_client.group_index)
        if not is_comlaint_sent:
            is_allright_sent_list[dkg_client.node_id] = True
            send_allright(dkg_client, web3)

        if len(dkg_fail_filter.get_all_entries()) > 0:
            # TERMINATE DKG
            raise FailedDKG("failed dut tot event FailedDKG")

        # LISTEN HERE TO COMPLAINTS ON THIS NODE
        is_complaint_received = False
        dkg_complaint_sent_filter = get_dkg_complaint_sent_filter(web3, dkg_client.group_index, dkg_client.node_ids[dkg_client.node_id])
        for event in dkg_complaint_sent_filter.get_all_entries():
            is_complaint_received = True
            to_response_index = 0
            while dkg_client.node_ids[to_response_index] != event["args"]["fromNodeIndex"]:
                to_response_index += 1
            response(dkg_client, dkg_client.node_id, web3)

        if len(dkg_fail_filter.get_all_entries()) > 0:
            # TERMINATE DKG
            raise FailedDKG("failed dut tot event FailedDKG")

        # TIMEOUT
        dkg_complaint_sent_filter = get_dkg_all_complaints_filter(web3, dkg_client.group_index)
        if len(dkg_complaint_sent_filter.get_all_entries()) == 0:
            while False in is_allright_sent_list:
                if time.time() - start_time_allright > 600:
                    break
                for event in dkg_all_data_received_filter.get_all_entries():
                    is_allright_sent_index = 0
                    while dkg_client.node_ids[is_allright_sent_index] != event["args"]["nodeIndex"]:
                        is_allright_sent_index += 1
                    is_allright_sent_list[is_allright_sent_index] = True
                sleep(1)

            for i in range(dkg_client.n):
                if not is_allright_sent_list[i]:
                    send_complaint(dkg_client, i, web3)
                    is_comlaint_sent = True

        is_comlaint_sent = len(dkg_complaint_sent_filter.get_all_entries())
        if is_comlaint_sent or is_complaint_received:
            while len(dkg_fail_filter.get_all_entries()) == 0:
                if time.time() - start_time_response > 600:
                    break
                sleep(1)
                continue

            if len(dkg_fail_filter.get_all_entries()) > 0:
                # TERMINATE DKG
                raise FailedDKG("failed dut tot event FailedDKG")
            else:
                # ELSE SEND A COMPLAINT
                print("COMPLAINT")
                send_complaint(dkg_client, complainted_node_index, web3)

        if True in is_allright_sent_list:
            if len(dkg_successful_filter.get_all_entries()) > 0:
                schains_data_contract = get_schains_data_contract(web3)
                common_public_key = schains_data_contract.functions.getGroupsPublicKey(dkg_client.group_index).call()

                with open(secret_key_share_filepath, 'w') as outfile:
                    json.dump({"secret_key :": dkg_client.secret_key_share,
                                "common_public_key :": common_public_key,
                                "public_key :": dkg_client.public_key}, outfile)


def get_secret_key_share_filepath(schain_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_id, 'secret_key.json')
