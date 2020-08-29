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
import shutil
import os
from itertools import chain

from web3 import Web3
from Crypto.Hash import keccak

from skale.dataclasses.skaled_ports import SkaledPorts

from core.schains.ssl import get_ssl_filepath
from core.schains.helper import get_schain_config_filepath, get_tmp_schain_config_filepath
from tools.configs.containers import DATA_DIR_CONTAINER_PATH

from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.helper import read_json
from tools.configs.schains import STATIC_SCHAIN_PARAMS_FILEPATH
from tools.configs.containers import LOCAL_IP
from tools.iptables import NodeEndpoint


def get_static_schain_params():
    return read_json(STATIC_SCHAIN_PARAMS_FILEPATH)


def get_context_contract():
    return get_static_schain_params()['context_contract']


def fix_address(address):
    return Web3.toChecksumAddress(address)


def get_chain_id(schain_name):
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(schain_name.encode("utf-8"))
    hash_ = keccak_hash.hexdigest()
    hash_ = hash_[:13]			# use 52 bits
    return "0x" + hash_


def _string_to_storage(slot: int, string: str) -> dict:
    # https://solidity.readthedocs.io/en/develop/miscellaneous.html#bytes-and-string
    storage = dict()
    binary = string.encode()
    length = len(binary)
    if length < 32:
        binary += (2 * length).to_bytes(32 - length, 'big')
        storage[hex(slot)] = '0x' + binary.hex()
    else:
        storage[hex(slot)] = hex(2 * length + 1)

        keccak_hash = keccak.new(digest_bits=256)
        keccak_hash.update(slot.to_bytes(32, 'big'))
        offset = int.from_bytes(keccak_hash.digest(), 'big')

        def chunks(size, source):
            for i in range(0, len(source), size):
                yield source[i:i + size]

        for index, data in enumerate(chunks(32, binary)):
            if len(data) < 32:
                data += int(0).to_bytes(32 - len(data), 'big')
            storage[hex(offset + index)] = '0x' + data.hex()
    return storage


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
            break

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


def get_schain_env():
    return {
        "SEGFAULT_SIGNALS": 'all'
    }


def get_schain_container_cmd(schain_name, public_key=None, start_ts=None):
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
    config_filepath = get_schain_config_filepath(schain_name, in_schain_container=True)
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


def parse_public_key_info(bls_public_key):
    public_key_list = bls_public_key.split(':')
    return {
        'blsPublicKey0': str(public_key_list[0]),
        'blsPublicKey1': str(public_key_list[1]),
        'blsPublicKey2': str(public_key_list[2]),
        'blsPublicKey3': str(public_key_list[3])
    }


def get_bls_public_keys(schain_name, rotation_id):
    key_file = get_secret_key_share_filepath(schain_name, rotation_id)
    json_file = read_json(key_file)
    return json_file["bls_public_keys"]

def compose_public_key_info(bls_public_key):
    return {
        'blsPublicKey0': str(bls_public_key[0][0]),
        'blsPublicKey1': str(bls_public_key[0][1]),
        'blsPublicKey2': str(bls_public_key[1][0]),
        'blsPublicKey3': str(bls_public_key[1][1])
    }
