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

from core.schains.config.dir import schain_config_dir
from core.schains.config.helper import get_schain_ports, get_schain_config
from core.ima.schain import get_schain_ima_abi_filepath

import json
import logging
import os
from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH, SGX_SERVER_URL
from tools.configs.containers import CONTAINERS_INFO
from tools.configs.db import REDIS_URI
from tools.configs.ima import IMA_ENDPOINT, MAINNET_IMA_ABI_FILEPATH, IMA_STATE_CONTAINER_PATH
from tools.configs.schains import SCHAINS_DIR_PATH
from flask import g
from websocket import create_connection

logger = logging.getLogger(__name__)


@dataclass
class ImaEnv:
    schain_dir: str

    mainnet_proxy_path: str
    schain_proxy_path: str

    state_file: str

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
            'STATE_FILE': self.state_file,
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
        schain_dir=schain_config_dir(schain_name),
        mainnet_proxy_path=MAINNET_IMA_ABI_FILEPATH,
        schain_proxy_path=get_schain_ima_abi_filepath(schain_name),
        state_file=IMA_STATE_CONTAINER_PATH,
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
        tm_url_mainnet=REDIS_URI,
        cid_main_net=mainnet_chain_id,
        monitoring_port=node_info['imaMonitoringPort']
    )


def get_ima_version() -> str:
    return CONTAINERS_INFO['ima']['version']


def get_ima_monitoring_port(schain_name):
    schain_config = get_schain_config(schain_name)
    if schain_config:
        node_info = schain_config["skaleConfig"]["nodeInfo"]
        return int(node_info["imaMonitoringPort"])
    else:
        return None


def get_ima_container_statuses():
    containers_list = g.docker_utils.get_all_ima_containers(all=True, format=True)
    ima_containers = [{'name': container['name'], 'state': container['state']['Status']}
                      for container in containers_list]
    return ima_containers


def request_ima_healthcheck(endpoint):
    result, ws = None, None
    try:
        ws = create_connection(endpoint, timeout=5)
        ws.send('{ "id": 1, "method": "get_last_transfer_errors"}')
        result = ws.recv()
    finally:
        if ws and ws.connected:
            ws.close()
    logger.debug(f'Received {result}')
    if result:
        data_json = json.loads(result)
        data = data_json['last_transfer_errors']
    else:
        data = None
    return data


def get_ima_log_checks():
    ima_containers = get_ima_container_statuses()
    ima_healthchecks = []
    for schain_name in os.listdir(SCHAINS_DIR_PATH):
        error_text = None
        ima_healthcheck = []
        container_name = f'skale_ima_{schain_name}'

        cont_data = next((item for item in ima_containers if item["name"] == container_name), None)
        if cont_data is None:
            continue
        elif cont_data['state'] != 'running':
            error_text = 'IMA docker container is not running'
        else:
            try:
                ima_port = get_ima_monitoring_port(schain_name)
            except KeyError as err:
                logger.exception(err)
                error_text = repr(err)
            else:
                if ima_port is None:
                    continue
                endpoint = f'ws://localhost:{ima_port}'
                try:
                    ima_healthcheck = request_ima_healthcheck(endpoint)
                except Exception as err:
                    logger.info(f'Error occurred while checking IMA state on {endpoint}')
                    logger.exception(err)
                    error_text = repr(err)
        if ima_healthcheck is None:
            ima_healthcheck = []
            error_text = 'Request failed'
        ima_healthchecks.append({schain_name: {'error': error_text,
                                               'last_ima_errors': ima_healthcheck}})
    return ima_healthchecks
