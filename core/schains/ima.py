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

from dataclasses import dataclass

from core.schains.helper import get_schain_dir_path, get_schain_proxy_file_path
from core.schains.config.helper import get_schain_ports, get_schain_config

from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH, SGX_SERVER_URL
from tools.configs.containers import CONTAINERS_INFO
from tools.configs.ima import IMA_ENDPOINT, MAINNET_PROXY_PATH
from tools.configs.web3 import TM_URL


@dataclass
class ImaEnv:
    schain_dir: str

    mainnet_proxy_path: str
    schain_proxy_path: str

    schain_name: str
    schain_rpc_url: str
    mainnet_rpc_url: str
    node_number: int
    nodes_count: int

    sgx_url: str
    ecdsa_key_name: str
    sgx_ssl_key_path: str
    sgx_ssl_cert_path: str
    node_address: str

    tm_url_mainnet: str

    cid_main_net: int

    monitoring_port: int

    def to_dict(self):
        """Returns upper-case representation of the ImaEnv object"""
        return {
            'SCHAIN_DIR': self.schain_dir,
            'MAINNET_PROXY_PATH': self.mainnet_proxy_path,
            'SCHAIN_PROXY_PATH': self.schain_proxy_path,
            'SCHAIN_NAME': self.schain_name,
            'SCHAIN_RPC_URL': self.schain_rpc_url,
            'MAINNET_RPC_URL': self.mainnet_rpc_url,
            'NODE_NUMBER': self.node_number,
            'NODES_COUNT': self.nodes_count,
            'SGX_URL': self.sgx_url,
            'ECDSA_KEY_NAME': self.ecdsa_key_name,
            'SGX_SSL_KEY_PATH': self.sgx_ssl_key_path,
            'SGX_SSL_CERT_PATH': self.sgx_ssl_cert_path,
            'NODE_ADDRESS': self.node_address,
            'TM_URL_MAIN_NET': self.tm_url_mainnet,
            'CID_MAIN_NET': self.cid_main_net,
            'MONITORING_PORT': self.monitoring_port
        }


def get_current_node_from_nodes(node_id, schain_nodes):
    for node in schain_nodes['nodes']:
        if node['nodeID'] == node_id:
            return node


def get_localhost_http_endpoint(schain_name):
    ports = get_schain_ports(schain_name)
    return f'http://127.0.0.1:{ports["http"]}'


def get_public_http_endpoint(public_node_info, schain_name):
    ports = get_schain_ports(schain_name)
    return f'http://{public_node_info["ip"]}:{ports["http"]}'


def get_local_http_endpoint(node_info, schain_name):
    ports = get_schain_ports(schain_name)
    return f'http://{node_info["bindIP"]}:{ports["http"]}'


def schain_index_to_node_number(node):
    return int(node['schainIndex']) - 1


def get_ima_env(schain_name: str, mainnet_chain_id: int) -> ImaEnv:
    schain_config = get_schain_config(schain_name)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    schain_nodes = schain_config["skaleConfig"]["sChain"]
    public_node_info = get_current_node_from_nodes(node_info['nodeID'], schain_nodes)

    schain_index = schain_index_to_node_number(public_node_info)
    node_address = public_node_info['owner']

    return ImaEnv(
        schain_dir=get_schain_dir_path(schain_name),
        mainnet_proxy_path=MAINNET_PROXY_PATH,
        schain_proxy_path=get_schain_proxy_file_path(schain_name),
        schain_name=schain_name,
        schain_rpc_url=get_localhost_http_endpoint(schain_name),
        mainnet_rpc_url=IMA_ENDPOINT,
        node_number=schain_index,
        nodes_count=len(schain_nodes['nodes']),
        sgx_url=SGX_SERVER_URL,
        ecdsa_key_name=node_info['ecdsaKeyName'],
        sgx_ssl_key_path=SGX_SSL_KEY_FILEPATH,
        sgx_ssl_cert_path=SGX_SSL_CERT_FILEPATH,
        node_address=node_address,
        tm_url_mainnet=TM_URL,
        cid_main_net=mainnet_chain_id,
        monitoring_port=node_info['imaMonitoringPort']
    )


def get_ima_version() -> str:
    return CONTAINERS_INFO['ima']['version']
