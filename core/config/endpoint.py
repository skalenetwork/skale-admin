#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025-Present SKALE Labs
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

from typing import Dict

# skaled RPC listeners move this far up inside the chain's port block when nginx serves them
RPC_PROXY_PORT_SHIFT = 32


def get_base_port_from_config(config: Dict | None) -> int:
    if config is None:
        return 0
    return config['skaleConfig']['nodeInfo']['basePort']


def get_chain_ports_from_config(config: Dict | None):
    if config is None:
        return {}
    node_info = config['skaleConfig']['nodeInfo']
    return {
        'http': int(node_info['httpRpcPort']),
        'ws': int(node_info['wsRpcPort']),
        'https': int(node_info['httpsRpcPort']),
        'wss': int(node_info['wssRpcPort']),
    }


def get_internal_chain_ports(ports: dict) -> dict:
    """Ports skaled listens on while nginx holds the public ones"""
    return {role: port + RPC_PROXY_PORT_SHIFT for role, port in ports.items()}


def _get_chain_rpc_ports_from_config(config: dict) -> tuple[int, int]:
    node_info = config['skaleConfig']['nodeInfo']
    return int(node_info['httpRpcPort']), int(node_info['wsRpcPort'])


def get_local_chain_http_endpoint_from_config(config: dict, rpc_proxy_mode: bool = False) -> str:
    """Local skaled endpoint, bypassing nginx when skaled runs on the internal ports"""
    http_port, _ = _get_chain_rpc_ports_from_config(config)
    if rpc_proxy_mode:
        http_port += RPC_PROXY_PORT_SHIFT
    return f'http://127.0.0.1:{http_port}'
