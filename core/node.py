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
import os
import platform
import shutil
import socket
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import psutil
import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout
from skale import SkaleManager
from skale.transactions.exceptions import TransactionLogicError
from skale.types.node import NodeId, NodeWithChangeIp
from skale.types.schain import SchainHash, SchainName
from skale.utils.exceptions import InvalidNodeIdError
from skale.utils.helper import ip_from_bytes
from skale.utils.web3_utils import public_key_to_address

from core.manager_cache import ManagerCache
from core.monitoring import update_monitoring_services
from core.node_config import NodeConfig
from tools.constants import CHAIN_STATE_PATH, CHECK_REPORT_PATH, META_FILEPATH
from tools.helper import is_fair, is_passive, read_json
from tools.str_formatters import arguments_list_string
from tools.wallet_utils import check_required_balance

logger = logging.getLogger(__name__)

WATCHDOG_PORT = 3009
CHANGE_IP_DELAY = 300

try:
    from sh import lsmod
except ImportError:
    logger.warning('Could not import lsmod from sh package')


class NodeStatus(Enum):
    """This class contains possible node statuses"""

    ACTIVE = 0
    LEAVING = 1
    FROZEN = 2
    IN_MAINTENANCE = 3
    LEFT = 4
    NOT_CREATED = 5


class NodeExitStatus(Enum):
    """This class contains possible node exit statuses"""

    ACTIVE = 0
    IN_PROGRESS = 1
    WAIT_FOR_ROTATIONS = 2
    IN_MAINTENANCE = 3
    COMPLETED = 4


class SchainExitStatus(Enum):
    """This class contains possible schain exit statuses"""

    ACTIVE = 0
    LEAVING = 1
    LEFT = 2


DOCKER_LVMPY_BLOCK_SIZE_URL = 'http://127.0.0.1:7373/physical-volume-size'


class Node:
    """This class contains node registration logic"""

    def __init__(self, skale: SkaleManager, config: NodeConfig):
        self.skale = skale
        self.config = config

    def register(
        self,
        ip,
        public_ip,
        port,
        name,
        domain_name,
        gas_limit=None,
        gas_price=None,
        skip_dry_run=False,
    ):
        """
        Main node registration function.

        Parameters:
        ip (str): P2P IP address that will be assigned to the node
        public_ip (str): Public IP address that will be assigned to the node
        port (int): Base port that will be used for sChains on the node
        name (str): Node name
        domain_name (str): Domain name

        Returns:
        dict: Execution status and node config
        """
        if self.config.id is not None:
            return self._error(
                f'Node is already installed on this machine. Node ID: {self.config.id}'
            )
        if not check_required_balance(self.skale):
            return self._error('Insufficient funds, re-check your wallet')

        if not self.skale.nodes.is_node_name_available(name):
            return self._error(f'Node name is already taken: {name}')

        if not self.skale.nodes.is_node_ip_available(ip):
            return self._error(f'Node IP is already taken: {ip}')

        node_id = self.create_node_on_contracts(
            ip, public_ip, port, name, domain_name, gas_limit, gas_price, skip_dry_run
        )
        if node_id < 0:
            return self._error(f'Node registration failed: {ip}:{port}, name: {name}')
        self.config.id = self.skale.nodes.node_name_to_index(name)

        self.config.name = name
        self.config.ip = ip

        update_monitoring_services(public_ip, self.config.id, self.skale.manager.address)
        return self._ok(data=self.config.all())

    def create_node_on_contracts(
        self,
        ip,
        public_ip,
        port,
        name,
        domain_name,
        gas_limit=None,
        gas_price=None,
        skip_dry_run=False,
    ):
        self._log_node_info('Node registration started', ip, public_ip, port, name)
        try:
            self.skale.manager.create_node(
                ip=ip,
                port=int(port),
                name=name,
                public_ip=public_ip,
                domain_name=domain_name,
                gas_limit=gas_limit,
                gas_price=gas_price,
                skip_dry_run=skip_dry_run,
                wait_for=True,
            )
        except TransactionLogicError:
            logger.exception('Node creation failed')
            return -1
        self._log_node_info('Node successfully registered', ip, public_ip, port, name)
        return self.skale.nodes.node_name_to_index(name)

    def exit(self, opts):
        schains_list = self.skale.schains.active_schains_for_node(self.config.id)
        exit_count = len(schains_list) or 1
        for _ in range(exit_count):
            try:
                self.skale.manager.node_exit(self.config.id, wait_for=True)
            except TransactionLogicError:
                logger.exception('Node rotation failed')

    def get_exit_status(self):
        active_schains = self.skale.schains.active_schains_for_node(self.config.id)
        schain_statuses = [
            {'name': schain.name, 'status': SchainExitStatus.ACTIVE.name}
            for schain in active_schains
        ]
        rotated_schains = self.skale.node_rotation.get_leaving_history(self.config.id)
        current_time = time.time()
        for schain in rotated_schains:
            if current_time > schain['finished_rotation']:
                status = SchainExitStatus.LEFT
            else:
                status = SchainExitStatus.LEAVING
            schain_name = self.skale.schains.get(schain['schain_id']).name
            if not schain_name:
                schain_name = '[REMOVED]'
            schain_statuses.append({'name': schain_name, 'status': status.name})
        node_status = NodeExitStatus(self.skale.nodes.node_status(self.config.id))
        exit_time = self.skale.nodes.node_finish_time(self.config.id)
        if node_status == NodeExitStatus.WAIT_FOR_ROTATIONS and current_time >= exit_time:
            node_status = NodeExitStatus.COMPLETED
        return {'status': node_status.name, 'data': schain_statuses, 'exit_time': exit_time}

    def set_maintenance_on(self):
        if NodeStatus(self.info['status']) != NodeStatus.ACTIVE:
            return self._error('Node should be active')
        try:
            self.skale.nodes.set_node_in_maintenance(self.config.id)
        except TransactionLogicError:
            return self._error('Moving node to maintenance mode failed')
        return self._ok()

    def set_maintenance_off(self):
        if NodeStatus(self.info['status']) != NodeStatus.IN_MAINTENANCE:
            return self._error('Node is not in maintenance mode')
        if NodeStatus(self.info['status']) != NodeStatus.IN_MAINTENANCE:
            err_msg = 'Node is not in maintenance mode'
            logger.error(err_msg)
            return {'status': 1, 'errors': [err_msg]}
        try:
            self.skale.nodes.remove_node_from_in_maintenance(self.config.id)
        except TransactionLogicError:
            return self._error('Removing node from maintenance mode failed')
        return self._ok()

    def set_domain_name(self, domain_name: str) -> dict:
        try:
            self.skale.nodes.set_domain_name(self.config.id, domain_name)
        except TransactionLogicError as err:
            return self._error(str(err))
        return self._ok()

    def _ok(self, data=None):
        return {'status': 'ok', 'data': data}

    def _error(self, err_msg):
        logger.error(err_msg)
        return {'status': 'error', 'errors': [err_msg]}

    def _log_node_info(self, title, ip, public_ip, port, name):
        log_params = {'IP': ip, 'Public IP': public_ip, 'Port': port, 'Name': name}
        logger.info(arguments_list_string(log_params, title))

    @property
    def info(self):
        _id = self.config.id
        if _id is not None:
            try:
                raw_info = self.skale.nodes.get(_id)
                return self._transform_node_info(raw_info, _id)
            except InvalidNodeIdError:
                logger.warning(f'Node with ID {_id} does not exist on contracts')
        return {'status': NodeStatus.NOT_CREATED.value, 'id': _id}

    def _transform_node_info(self, node_info, node_id):
        node_info['ip'] = ip_from_bytes(node_info['ip'])
        node_info['publicIP'] = ip_from_bytes(node_info['publicIP'])
        node_info['status'] = _get_node_status(node_info)
        node_info['id'] = node_id
        node_info['publicKey'] = node_info['publicKey']
        node_info['owner'] = public_key_to_address(node_info['publicKey'])
        return node_info


def _get_node_status(node_info):
    finish_time = node_info['finish_time']
    status = NodeStatus(node_info['status'])
    if status == NodeStatus.FROZEN and finish_time < time.time():
        return NodeStatus.LEFT.value
    return status.value


def get_block_device_size() -> int:
    """Returns block device size in bytes"""
    try:
        if is_passive() or is_fair():
            total, _, _ = shutil.disk_usage(CHAIN_STATE_PATH)
            return total
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.exception(f'Error getting block device size: {e}')
        return -1
    try:
        response = requests.get(DOCKER_LVMPY_BLOCK_SIZE_URL, json={'Name': None}, timeout=10)
        data = response.json()
        if data['Err'] != '':
            err = data['Err']
            logger.error(f'Lvmpy returned an error {err}')
            return -1
        return data['Size']
    except (RequestException, ConnectionError, Timeout, HTTPError) as e:
        logger.exception(f'Error getting block device size: {e}')
        return -1


def get_node_hardware_info() -> dict:
    system_release = f'{platform.system()}-{platform.release()}'
    uname_version = platform.uname().version
    attached_storage_size = get_block_device_size()
    return {
        'cpu_total_cores': psutil.cpu_count(logical=True),
        'cpu_physical_cores': psutil.cpu_count(logical=False),
        'memory': psutil.virtual_memory().total,
        'swap': psutil.swap_memory().total,
        'mem_used': psutil.virtual_memory().used,
        'mem_available': psutil.virtual_memory().available,
        'system_release': system_release,
        'uname_version': uname_version,
        'attached_storage_size': attached_storage_size,
    }


def get_meta_info() -> dict:
    return read_json(META_FILEPATH)


def get_skale_node_version():
    return get_meta_info()['config_stream']


def is_btrfs_loaded():
    modules = list(filter(lambda s: s.startswith('btrfs'), lsmod().split('\n')))
    return modules != []


def get_btrfs_info() -> dict:
    return {'kernel_module': is_btrfs_loaded()}


def get_check_report(report_path: Path = CHECK_REPORT_PATH) -> Dict:
    if not os.path.isfile(report_path):
        return {}
    with open(report_path) as report_file:
        return json.load(report_file)


def get_current_nodes(
    skale: SkaleManager, schain_hash: SchainHash, manager_cache: ManagerCache | None = None
) -> List[NodeWithChangeIp]:
    if skale.schains_internal.is_empty_schain_hash(schain_hash):
        return []
    ids = skale.schains_internal.node_ids_for_schain_hash(schain_hash)

    cached_by_id: dict[NodeId, NodeWithChangeIp] = {}
    if manager_cache is not None:
        cached_by_id = {node['id']: node for node in manager_cache.nodes}

    current_nodes: list[NodeWithChangeIp] = []
    for node_id in ids:
        if node_id in cached_by_id:
            current_nodes.append(cached_by_id[node_id])
        else:
            node = skale.nodes.get_with_change_ip(node_id)
            current_nodes.append(node)

    return current_nodes


def get_current_ips(current_nodes: List[NodeWithChangeIp]) -> list[str]:
    return [node['ip'] for node in current_nodes]


def get_max_ip_change_ts(current_nodes: List[NodeWithChangeIp]) -> Optional[int]:
    max_ip_change_ts = max(current_nodes, key=lambda node: node['ip_change_ts'])['ip_change_ts']
    return None if max_ip_change_ts == 0 else max_ip_change_ts


def calc_reload_ts(current_nodes: List[NodeWithChangeIp], node_index: int) -> int | None:
    max_ip_change_ts = get_max_ip_change_ts(current_nodes)
    if max_ip_change_ts is None:
        return None
    return max_ip_change_ts + get_node_delay(node_index)


def get_node_delay(node_index: int) -> int:
    """
    Returns delay for node in seconds.
    Example: for node with index 3 and delay 300 it will be 1200 seconds
    """
    return CHANGE_IP_DELAY * (node_index + 1)


def get_node_index_in_group(
    skale: SkaleManager, schain_name: SchainName, node_id: NodeId
) -> Optional[int]:
    """Returns node index in group or None if node is not in group"""
    try:
        node_ids = skale.schains_internal.node_ids_for_schain(schain_name)
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
        node_ids = skale.nodes.validator_node_indices(node['validator_id'])

        try:
            node_ids.remove(node_id)
        except ValueError:
            logger.warning(f'node_id: {node_id} was not found in validator nodes: {node_ids}')

        res = []
        for node_id in node_ids:
            ip_bytes = skale.nodes.contract.functions.getNodeIP(node_id).call()
            ip = ip_from_bytes(ip_bytes)
            res.append([node_id, ip, is_port_open(ip, WATCHDOG_PORT)])
        logger.info(f'validator_nodes check - node_id: {node_id}, res: {res}')
    except Exception as err:
        return {'status': 1, 'errors': [err]}
    return {'status': 0, 'data': res}
