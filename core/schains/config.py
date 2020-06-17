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

import json
import logging
import shutil
import os
from itertools import chain

from skale.schain_config.generator import generate_skale_schain_config
from skale.dataclasses.skaled_ports import SkaledPorts

from core.schains.ssl import get_ssl_filepath
from core.schains.helper import (read_base_config, read_ima_data,
                                 get_schain_config_filepath, get_tmp_schain_config_filepath)
from core.schains.volume import get_resource_allocation_info, get_allocation_option_name
from tools.sgx_utils import SGX_SERVER_URL
from tools.configs.containers import DATA_DIR_CONTAINER_PATH

from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.configs.containers import CONTAINERS_INFO, LOCAL_IP
from tools.configs.ima import IMA_ENDPOINT, MAINNET_PROXY_PATH
from tools.configs.schains import IMA_DATA_FILEPATH
from tools.iptables import NodeEndpoint
from tools.helper import read_json

logger = logging.getLogger(__name__)


def generate_schain_config(skale, schain_name, node_id, rotation_id):
    base_config = read_base_config()
    ima_data = read_ima_data()
    wallets = generate_wallets_config(schain_name, rotation_id)
    ima_mainnet_url = IMA_ENDPOINT
    ima_mp_schain, ima_mp_mainnet = get_mp_addresses()
    options = CONTAINERS_INFO['schain']['config_options']
    config_opts = dict()
    if options.get('rotateAfterBlock'):
        config_opts['rotate_after_block'] = options.get('rotateAfterBlock')
    if options.get('snapshotIntervalMs'):
        config_opts['snapshot_interval_ms'] = options.get('snapshotIntervalMs')
    if options.get('emptyBlockIntervalMs'):
        config_opts['empty_block_interval_ms'] = options.get('emptyBlockIntervalMs')

    resource_allocation = get_resource_allocation_info()
    schain = skale.schains_data.get_by_name(schain_name)  # todo: optimize to avoid multiple calls
    schain_size_name = get_allocation_option_name(schain)
    custom_schain_config_fields = {
        'storageLimit': resource_allocation['schain']['storage_limit'][schain_size_name]
    }
    config = generate_skale_schain_config(
        skale=skale,
        schain_name=schain_name,
        node_id=node_id,
        base_config=base_config,
        ima_mainnet=ima_mainnet_url,
        ima_mp_schain=ima_mp_schain,
        ima_mp_mainnet=ima_mp_mainnet,
        wallets=wallets,
        ima_data=ima_data,
        custom_schain_config_fields=custom_schain_config_fields,
        **config_opts
    )
    config['skaleConfig']['nodeInfo']['bindIP'] = '0.0.0.0'
    return config


def get_mp_addresses():
    ima_abi = read_json(MAINNET_PROXY_PATH)
    schain_ima_abi = read_json(IMA_DATA_FILEPATH)
    ima_mp_schain = schain_ima_abi['message_proxy_chain_address']
    ima_mp_mainnet = ima_abi['message_proxy_mainnet_address']
    return ima_mp_schain, ima_mp_mainnet


def generate_wallets_config(schain_name, rotation_id):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    secret_key_share_config = read_json(secret_key_share_filepath)
    wallets = {
        'ima': {
            'url': SGX_SERVER_URL,
            'keyShareName': secret_key_share_config['key_share_name'],
            't': secret_key_share_config['t'],
            'n': secret_key_share_config['n']
        }
    }
    common_public_keys = secret_key_share_config['common_public_key']
    for (i, value) in enumerate(common_public_keys):
        name = 'insecureBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    public_keys = secret_key_share_config['public_key']
    for (i, value) in enumerate(public_keys):
        name = 'insecureCommonBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    return wallets


def save_schain_config(schain_config, schain_name):
    schain_config_filepath = get_schain_config_filepath(schain_name)
    with open(schain_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)

    return schain_config_filepath


def update_schain_config(schain_config, schain_name):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    with open(tmp_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)
    config_filepath = get_schain_config_filepath(schain_name)
    shutil.move(tmp_config_filepath, config_filepath)


def get_schain_ports(schain_name):
    config = get_schain_config(schain_name)
    return get_schain_ports_from_config(config)


def get_schain_ports_from_config(config):
    if config is None:
        return {}
    node_info = config["skaleConfig"]["nodeInfo"]
    return {
        'http': int(node_info["httpRpcPort"]),
        'ws': int(node_info["wsRpcPort"]),
        'https': int(node_info["httpsRpcPort"]),
        'wss': int(node_info["wssRpcPort"])
    }


def get_skaled_rpc_endpoints_from_config(config):
    if config is None:
        return []
    node_info = config["skaleConfig"]["nodeInfo"]
    return [
        NodeEndpoint(ip=None, port=node_info['httpRpcPort']),
        NodeEndpoint(ip=None, port=node_info['wsRpcPort']),
        NodeEndpoint(ip=None, port=node_info['httpsRpcPort']),
        NodeEndpoint(ip=None, port=node_info['wssRpcPort'])
    ]


def get_snapshots_endpoints_from_config(config):
    # TODO: Add this endpoints
    return []


def get_skaled_http_snapshot_address(schain_name):
    config = get_schain_config(schain_name)
    return get_skaled_http_snapshot_address_from_config(config)


def get_skaled_http_snapshot_address_from_config(config):
    node_id = config['skaleConfig']['nodeInfo']['nodeID']
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']
    from_node = None
    for node_data in schain_nodes_config:
        if node_data['nodeID'] != node_id:
            from_node = node_data

    return NodeEndpoint(from_node['ip'], from_node['basePort'] +
                        SkaledPorts.HTTP_JSON.value)


def get_skaled_http_address(schain_name):
    config = get_schain_config(schain_name)
    return get_skaled_http_address_from_config(config)


def get_skaled_http_address_from_config(config):
    node = config['skaleConfig']['nodeInfo']
    return NodeEndpoint(LOCAL_IP, node['httpRpcPort'])


def get_consensus_ips_with_ports(schain_name):
    config = get_schain_config(schain_name)
    return get_consensus_endpoints_from_config(config)


def get_consensus_endpoints_from_config(config):
    if config is None:
        return []
    node_id = config['skaleConfig']['nodeInfo']['nodeID']
    base_port = config['skaleConfig']['nodeInfo']['basePort']
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']

    node_endpoints = list(chain.from_iterable(
        (
            NodeEndpoint(
                node_data['publicIP'],
                base_port + SkaledPorts.PROPOSAL.value),
            NodeEndpoint(
                node_data['publicIP'],
                base_port + SkaledPorts.CATCHUP.value),
            NodeEndpoint(
                node_data['publicIP'],
                base_port + SkaledPorts.BINARY_CONSENSUS.value
            ),
            NodeEndpoint(
                node_data['publicIP'],
                base_port + SkaledPorts.ZMQ_BROADCAST.value
            )
        )
        for node_data in schain_nodes_config
        if node_data['nodeID'] != node_id
    ))
    return node_endpoints


def get_allowed_endpoints(schain_name):
    config = get_schain_config(schain_name)
    return [
        *get_consensus_endpoints_from_config(config),
        *get_skaled_rpc_endpoints_from_config(config),
        *get_snapshots_endpoints_from_config(config)
    ]


def get_schain_config(schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        return None
    with open(config_filepath) as f:
        schain_config = json.load(f)
    return schain_config


def get_schain_env(schain_name, public_key=None, start_ts=None):
    container_opts = get_schain_container_opts(schain_name, public_key, start_ts)
    return {
        "OPTIONS": container_opts,
        "SEGFAULT_SIGNALS": 'all'
    }


def get_schain_container_opts(schain_name, public_key=None, start_ts=None):
    opts = get_schain_container_base_opts(schain_name)
    if public_key and str(start_ts):
        sync_opts = get_schain_container_sync_opts(schain_name, public_key, start_ts)
        opts += sync_opts
    return opts


def get_schain_container_sync_opts(schain_name, public_key, start_ts):
    endpoint = get_skaled_http_snapshot_address(schain_name)
    url = f'http://{endpoint.ip}:{endpoint.port}'
    return (
        f'--download-snapshot {url} '
        f'--public-key {public_key} '
        f'--start-timestamp {start_ts} '
    )


def get_schain_container_base_opts(schain_name, log_level=4):
    config_filepath = get_schain_config_filepath(schain_name)
    ssl_key, ssl_cert = get_ssl_filepath()
    ports = get_schain_ports(schain_name)
    return (
        f'--config {config_filepath} '
        f'-d {DATA_DIR_CONTAINER_PATH} '
        f'--ipcpath {DATA_DIR_CONTAINER_PATH} '
        f'--http-port {ports["http"]} '
        f'--https-port {ports["https"]} '
        f'--ws-port {ports["ws"]} '
        f'--wss-port {ports["wss"]} '
        f'--ssl-key {ssl_key} '
        f'--ssl-cert {ssl_cert} '
        f'-v {log_level} '
        f'--web3-trace '
        f'--enable-debug-behavior-apis '
        f'--aa no '
    )


def get_schain_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpRpcPort"]), int(node_info["wsRpcPort"])


def get_schain_ssl_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpsRpcPort"]), int(node_info["wssRpcPort"])
