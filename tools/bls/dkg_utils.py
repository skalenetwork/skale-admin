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
import os

from tools.configs import NODE_DATA_PATH
from tools.bls.dkg_client import DKGClient, DkgError

logger = logging.getLogger(__name__)


class DkgFailedError(DkgError):
    pass


def init_dkg_client(schain_config, skale, n, t, sgx_eth_key_name):
    node_id_dkg = -1
    node_id_contract = schain_config["skaleConfig"]["nodeInfo"]["nodeID"]
    public_keys = [0] * n
    node_ids_contract = dict()
    node_ids_dkg = dict()
    for i, node in enumerate(schain_config["skaleConfig"]["sChain"]["nodes"]):
        if node["nodeID"] == schain_config["skaleConfig"]["nodeInfo"]["nodeID"]:
            node_id_dkg = i

        node_ids_contract[node["nodeID"]] = i
        node_ids_dkg[i] = node["nodeID"]

        public_keys[i] = node["publicKey"]

    schain_name = schain_config["skaleConfig"]["sChain"]["schainName"]

    dkg_client = DKGClient(
        node_id_dkg, node_id_contract, skale, t, n, schain_name,
        public_keys, node_ids_dkg, node_ids_contract, sgx_eth_key_name
    )
    return dkg_client


def generate_bls_key_name(group_index_str, node_id, dkg_id):
    return (
            "BLS_KEY:SCHAIN_ID:"
            f"{group_index_str}"
            ":NODE_ID:"
            f"{str(node_id)}"
            ":DKG_ID:"
            f"{str(dkg_id)}"
        )


def generate_poly_name(group_index_str, node_id, dkg_id):
    return (
            "POLY:SCHAIN_ID:"
            f"{group_index_str}"
            ":NODE_ID:"
            f"{str(node_id)}"
            ":DKG_ID:"
            f"{str(dkg_id)}"
        )


def generate_bls_key(dkg_client, bls_key_name):
    return dkg_client.generate_key(bls_key_name)


def broadcast(dkg_client, poly_name):
    dkg_client.broadcast(poly_name)


def send_complaint(dkg_client, index):
    dkg_client.send_complaint(index)


def response(dkg_client, from_node_index):
    dkg_client.response(from_node_index)


def send_alright(dkg_client):
    dkg_client.alright()


def get_broadcasted_data(dkg_client, from_node):
    return dkg_client.get_broadcasted_data(from_node)


def is_all_data_received(dkg_client, from_node):
    return dkg_client.is_all_data_received(from_node)


def get_complaint_data(dkg_client):
    return dkg_client.get_complaint_data()


def get_secret_key_share_filepath(schain_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_id, 'secret_key.json')
