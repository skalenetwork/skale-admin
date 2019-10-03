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
from time import sleep

from core.schains_helper import get_schain_config_filepath
from tools.config import NODE_DATA_PATH
from tools.bls.dkg_utils import init_dkg_client, broadcast, get_dkg_filter, get_dkg_contract

def init_bls(web3, wallet, schain_name):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name)
    config_filepath = get_schain_config_filepath(schain_name)

    if not os.path.isfile(secret_key_share_filepath):

        with open(config_filepath, 'r') as infile:
            config_file = json.load(infile)

        n = len(config_file["skaleConfig"]["sChain"]["nodes"])
        t = (n * 2 + 1) // 3

        dkg_contract = get_dkg_contract(web3)
        dkg_filter = get_dkg_filter(web3)

        local_wallet = wallet.get_full()

        dkg_client = init_dkg_client(config_filepath, web3, local_wallet, n, t)
        broadcast(dkg_client, web3)

        is_received = [False] * n
        is_received[dkg_client.node_id] = True

        # start_listening = time.time()
        while False in is_received:

            # cur_time = time.time()
            # if start_listening - cur_time > 600:
            #    raise Exception("Too much time spent on running DKG-client, need to restart it from scratch")
            for event in dkg_filter.get_all_entries():

                #print('ev!!!', event)

                from_node = event["args"]["fromNode"]

                if (event["args"]["schainName"] == schain_name) and (
                        is_received[from_node] == False):
                    is_received[from_node] = True

                    dkg_client.RecieveAll(from_node, event)
                    print("Recieved by", dkg_client.node_id)
            sleep(1)

        with open(secret_key_share_filepath, 'w') as outfile:
            json.dump({"secret_key :": dkg_client.secret_key_share}, outfile)


def get_secret_key_share_filepath(schain_id):
    return os.path.join(NODE_DATA_PATH, construct_secret_key_share_filename(schain_id))


def construct_secret_key_share_filename(schain_id):
    return f'schain_{schain_id}_secret_key.json'
