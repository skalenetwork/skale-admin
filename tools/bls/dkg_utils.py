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

import coincurve
import json
from web3 import Web3

from tools.config import CUSTOM_CONTRACTS_PATH

from tools.bls.dkg_client import DKGClient

def init_dkg_client(schain_config_filepath, web3, wallet, n, t):
    with open(schain_config_filepath, 'r') as infile:
        config_file = json.load(infile)

    node_id = config_file["skaleConfig"]["nodeInfo"]["nodeID"]
    public_keys = [0] * n
    for node in config_file["skaleConfig"]["sChain"]["nodes"]:
        public_keys[node["nodeID"]] = coincurve.PublicKey(bytes.fromhex("04" + node["publicKey"]))

    schain_name = config_file["skaleConfig"]["sChain"]["schainName"]

    dkg_client = DKGClient(node_id, web3, wallet, t, n, schain_name, public_keys)
    return dkg_client

def broadcast(dkg_client, web3):
    dkg_client.Broadcast(get_dkg_contract(web3))

def send_complaint(dkg_client, index, web3):
    dkg_client.SendComplaint(index, get_dkg_contract(web3))

def response(dkg_client, web3):
    dkg_client.Response(event["args"]["fromNodeIndex"], get_dkg_contract(web3))

def send_allright(dkg_client, web3):
    dkg_client.Allright(get_dkg_contract(web3))

def get_dkg_filter(web3):
    contract = get_dkg_contract(web3)
    return contract.events.BroadcastAndKeyShare.createFilter(fromBlock = 1)

def get_dkg_contract(web3):
    custom_contracts_contracts_data = read_custom_contracts_data()
    dkg_contract_address = custom_contracts_contracts_data['skale_dkg_address']
    dkg_contract_abi = custom_contracts_contracts_data['skale_dkg_abi']

    return web3.eth.contract(address=Web3.toChecksumAddress(dkg_contract_address), abi=dkg_contract_abi)

def read_custom_contracts_data():
    with open(CUSTOM_CONTRACTS_PATH, encoding='utf-8') as data_file:
        return json.loads(data_file.read())
