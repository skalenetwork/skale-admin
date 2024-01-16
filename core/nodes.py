#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2024 SKALE Labs
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

import socket
import logging
from typing import List, Optional, TypedDict

from skale import Skale
from skale.utils.helper import ip_from_bytes
from skale.schain_config.generator import get_nodes_for_schain

from core.node import NodeStatus
from tools.configs import WATCHDOG_PORT, CHANGE_IP_DELAY

logger = logging.getLogger(__name__)


class ManagerNodeInfo(TypedDict):
    name: str
    ip: str
    publicIP: str
    port: int
    start_block: int
    last_reward_date: int
    finish_time: int
    status: int
    validator_id: int
    publicKey: str
    domain_name: str


class ExtendedManagerNodeInfo(ManagerNodeInfo):
    ip_change_ts: int


def get_current_nodes(skale: Skale, name: str) -> List[ExtendedManagerNodeInfo]:
    current_nodes: ManagerNodeInfo = get_nodes_for_schain(skale, name)
    for node in current_nodes:
        node['ip_change_ts'] = skale.nodes.get_last_change_ip_time(node['id'])
        node['ip'] = ip_from_bytes(node['ip'])
        node['publicIP'] = ip_from_bytes(node['publicIP'])
    return current_nodes


def get_current_ips(current_nodes: List[ExtendedManagerNodeInfo]) -> list[str]:
    return [node['ip'] for node in current_nodes]


def get_max_ip_change_ts(current_nodes: List[ExtendedManagerNodeInfo]) -> Optional[int]:
    max_ip_change_ts = max(current_nodes, key=lambda node: node['ip_change_ts'])['ip_change_ts']
    return None if max_ip_change_ts == 0 else max_ip_change_ts


def calc_reload_ts(current_nodes: List[ExtendedManagerNodeInfo], node_index: int) -> int:
    max_ip_change_ts = get_max_ip_change_ts(current_nodes)
    if max_ip_change_ts is None:
        return
    return max_ip_change_ts + get_node_delay(node_index)


def get_node_delay(node_index: int) -> int:
    """
    Returns delay for node in seconds.
    Example: for node with index 3 and delay 300 it will be 1200 seconds
    """
    return CHANGE_IP_DELAY * (node_index + 1)


def get_node_index_in_group(skale: Skale, schain_name: str, node_id: int) -> Optional[int]:
    """Returns node index in group or None if node is not in group"""
    try:
        node_ids = skale.schains_internal.get_node_ids_for_schain(schain_name)
        return node_ids.index(node_id)
    except ValueError:
        return None


def is_port_open(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((ip, int(port)))
        s.shutdown(1)
        return True
    except Exception:
        return False


def check_validator_nodes(skale, node_id):
    try:
        node = skale.nodes.get(node_id)
        node_ids = skale.nodes.get_validator_node_indices(node['validator_id'])

        try:
            node_ids.remove(node_id)
        except ValueError:
            logger.warning(
                f'node_id: {node_id} was not found in validator nodes: {node_ids}')

        res = []
        for node_id in node_ids:
            if str(skale.nodes.get_node_status(node_id)) == str(NodeStatus.ACTIVE.value):
                ip_bytes = skale.nodes.contract.functions.getNodeIP(
                    node_id).call()
                ip = ip_from_bytes(ip_bytes)
                res.append([node_id, ip, is_port_open(ip, WATCHDOG_PORT)])
        logger.info(f'validator_nodes check - node_id: {node_id}, res: {res}')
    except Exception as err:
        return {'status': 1, 'errors': [err]}
    return {'status': 0, 'data': res}
