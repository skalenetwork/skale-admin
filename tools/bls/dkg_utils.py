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
import coincurve
import json
from web3 import Web3

from tools.configs import NODE_DATA_PATH
from tools.configs.web3 import ABI_FILEPATH
from tools.bls.dkg_client import DKGClient


def init_dkg_client(schain_config_filepath, web3, wallet, n, t):
    with open(schain_config_filepath, 'r') as infile:
        config_file = json.load(infile)

    node_id_dkg = -1
    node_id_contract = config_file["skaleConfig"]["nodeInfo"]["nodeID"]
    public_keys = [0] * n
    i = 0
    node_ids_contract = dict()
    node_ids_dkg = dict()
    is_node_id_set = False
    for node in config_file["skaleConfig"]["sChain"]["nodes"]:
        if node["nodeID"] == config_file["skaleConfig"]["nodeInfo"]["nodeID"]:
            node_id_dkg = i

        node_ids_contract[node["nodeID"]] = i
        node_ids_dkg[i] = node["nodeID"]

        public_keys[i] = coincurve.PublicKey(bytes.fromhex("04" + node["publicKey"]))
        i += 1

    schain_name = config_file["skaleConfig"]["sChain"]["schainName"]

    dkg_client = DKGClient(node_id_dkg, node_id_contract, web3, wallet, t, n, schain_name, public_keys, node_ids_dkg, node_ids_contract)
    return dkg_client


def broadcast(dkg_client):
    dkg_client.Broadcast()


def send_complaint(dkg_client, index):
    dkg_client.SendComplaint(index)


def response(dkg_client):
    dkg_client.Response()


def send_allright(dkg_client):
    dkg_client.Allright()


def get_dkg_broadcast_filter(skale, group_index):
    contract = skale.dkg.contract
    return contract.events.BroadcastAndKeyShare.createFilter(fromBlock=0, argument_filters={
        'groupIndex': group_index})


def get_dkg_complaint_sent_filter(skale, group_index, to_node_index):
    contract = skale.dkg.contract
    return contract.events.ComplaintSent.createFilter(fromBlock=0,
                                                      argument_filters={'groupIndex': group_index,
                                                                        'toNodeIndex': to_node_index})


def get_dkg_all_complaints_filter(skale, group_index):
    contract = skale.dkg.contract
    return contract.events.ComplaintSent.createFilter(fromBlock=0,
                                                      argument_filters={'groupIndex': group_index})


def get_dkg_successful_filter(skale, group_index):
    contract = skale.dkg.contract
    return contract.events.SuccessfulDKG.createFilter(fromBlock=0,
                                                      argument_filters={'groupIndex': group_index})


def get_dkg_fail_filter(skale, group_index):
    contract = skale.dkg.contract
    return contract.events.FailedDKG.createFilter(fromBlock=0,
                                                  argument_filters={'groupIndex': group_index})


def get_dkg_all_data_received_filter(skale, group_index):
    contract = skale.dkg.contract
    return contract.events.AllDataReceived.createFilter(fromBlock=0, argument_filters={
        'groupIndex': group_index})


def get_dkg_bad_guy_filter(skale):
    contract = skale.dkg.contract
    return contract.events.BadGuy.createFilter(fromBlock=0)
  

def get_schains_data_contract(web3):
    custom_contracts_contracts_data = read_custom_contracts_data()
    schains_data_contract_address = custom_contracts_contracts_data['schains_data_address']
    schains_data_contract_abi = custom_contracts_contracts_data['schains_data_abi']

    return web3.eth.contract(address=Web3.toChecksumAddress(schains_data_contract_address),
                             abi=schains_data_contract_abi)


def read_custom_contracts_data():
    with open(ABI_FILEPATH, encoding='utf-8') as data_file:
        return json.loads(data_file.read())


def get_secret_key_share_filepath(schain_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_id, 'secret_key.json')
