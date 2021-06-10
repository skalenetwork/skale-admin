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
import platform
import psutil
import requests
import time
from enum import Enum

from skale.transactions.result import TransactionFailedError
from skale.utils.exceptions import InvalidNodeIdError
from skale.utils.helper import ip_from_bytes
from skale.utils.web3_utils import public_key_to_address, to_checksum_address

from core.filebeat import run_filebeat_service

from tools.configs import META_FILEPATH
from tools.configs.filebeat import MONITORING_CONTAINERS
from tools.configs.resource_allocation import DISK_MOUNTPOINT_FILEPATH
from tools.configs.web3 import NODE_REGISTER_CONFIRMATION_BLOCKS
from tools.helper import read_json
from tools.str_formatters import arguments_list_string
from tools.wallet_utils import check_required_balance

logger = logging.getLogger(__name__)


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
    COMPLETED = 3


class SchainExitStatus(Enum):
    """This class contains possible schain exit statuses"""
    ACTIVE = 0
    LEAVING = 1
    LEFT = 2


DOCKER_LVMPY_BLOCK_SIZE_URL = 'http://127.0.0.1:7373/physical-volume-size'


class Node:
    """This class contains node registration logic"""
    def __init__(self, skale, config):
        self.skale = skale
        self.config = config

    def register(self, ip, public_ip, port, name, domain_name,
                 gas_limit=None, gas_price=None, skip_dry_run=False):
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
                f'Node is already installed on this machine. '
                f'Node ID: {self.config.id}'
            )
        node_id = self.get_node_id_from_contracts(name, ip)
        if node_id < 0:
            if not check_required_balance(self.skale):
                return self._error(
                    'Insufficient funds, re-check your wallet')

            if not self.skale.nodes.is_node_name_available(name):
                return self._error(f'Node name is already taken: {name}')

            if not self.skale.nodes.is_node_ip_available(ip):
                return self._error(f'Node IP is already taken: {ip}')

            node_id = self.create_node_on_contracts(
                ip, public_ip, port, name, domain_name,
                gas_limit, gas_price, skip_dry_run
            )
            if node_id < 0:
                return self._error(
                    f'Node registration failed: {ip}:{port}, name: {name}'
                )
        self.config.id = self.skale.nodes.node_name_to_index(name)

        self.config.name = name
        self.config.ip = ip

        if MONITORING_CONTAINERS:
            run_filebeat_service(public_ip, self.config.id, self.skale)
        return self._ok(data=self.config.all())

    def create_node_on_contracts(self, ip, public_ip, port, name, domain_name,
                                 gas_limit=None, gas_price=None,
                                 skip_dry_run=False):
        self._log_node_info('Node registration started', ip,
                            public_ip, port, name)
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
                confirmation_blocks=NODE_REGISTER_CONFIRMATION_BLOCKS
            )
        except TransactionFailedError:
            logger.exception('Node creation failed')
            return -1
        self._log_node_info('Node successfully registered', ip,
                            public_ip, port, name)
        return self.skale.nodes.node_name_to_index(name)

    def get_node_id_from_contracts(self, name, ip) -> int:
        if self.config.name is None:
            return -1
        node_id = self.skale.nodes.node_name_to_index(self.config.name)
        if node_id == 0:
            try:
                node_data = self.skale.nodes.get(node_id)
            except InvalidNodeIdError:
                return -1
            public_key = node_data['publicKey']
            data_address = to_checksum_address(
                public_key_to_address(public_key)
            )
            if data_address == self.skale.wallet.address and \
                name == node_data['name'] and \
                    ip == node_data['ip']:
                node_id = 0
            else:
                node_id = -1
        return node_id

    def exit(self, opts):
        schains_list = self.skale.schains.get_active_schains_for_node(
            self.config.id)
        exit_count = len(schains_list) or 1
        for _ in range(exit_count):
            try:
                self.skale.manager.node_exit(self.config.id, wait_for=True)
            except TransactionFailedError:
                logger.exception('Node rotation failed')

    def get_exit_status(self):
        active_schains = self.skale.schains.get_active_schains_for_node(
            self.config.id)
        schain_statuses = [
            {
                'name': schain['name'],
                'status': SchainExitStatus.ACTIVE.name
            }
            for schain in active_schains
        ]
        rotated_schains = self.skale.node_rotation.get_leaving_history(
            self.config.id)
        current_time = time.time()
        for schain in rotated_schains:
            if current_time > schain['finished_rotation']:
                status = SchainExitStatus.LEFT
            else:
                status = SchainExitStatus.LEAVING
            schain_name = self.skale.schains.get(schain['id'])['name']
            if not schain_name:
                schain_name = '[REMOVED]'
            schain_statuses.append(
                {'name': schain_name, 'status': status.name}
            )
        node_status = NodeExitStatus(
            self.skale.nodes.get_node_status(self.config.id))
        exit_time = self.skale.nodes.get_node_finish_time(self.config.id)
        if node_status == NodeExitStatus.WAIT_FOR_ROTATIONS and \
                current_time >= exit_time:
            node_status = NodeExitStatus.COMPLETED
        return {'status': node_status.name, 'data': schain_statuses,
                'exit_time': exit_time}

    def set_maintenance_on(self):
        if NodeStatus(self.info['status']) != NodeStatus.ACTIVE:
            self._error('Node should be active')
        try:
            self.skale.nodes.set_node_in_maintenance(self.config.id)
        except TransactionFailedError:
            self._error('Moving node to maintenance mode failed')
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
        except TransactionFailedError:
            return self._error('Removing node from maintenance mode failed')
        return self._ok()

    def set_domain_name(self, domain_name: str) -> dict:
        try:
            self.skale.nodes.set_domain_name(self.config.id, domain_name)
        except TransactionFailedError as err:
            return self._error(str(err))
        return self._ok()

    def _ok(self, data=None):
        return {'status': 'ok', 'data': data}

    def _error(self, err_msg):
        logger.error(err_msg)
        return {'status': 'error', 'errors': [err_msg]}

    def _log_node_info(self, title, ip, public_ip, port, name):
        log_params = {'IP': ip, 'Public IP': public_ip,
                      'Port': port, 'Name': name}
        logger.info(arguments_list_string(log_params, title))

    @property
    def info(self):
        _id = self.config.id
        if _id is not None:
            raw_info = self.skale.nodes.get(_id)
            return self._transform_node_info(raw_info, _id)
        return {'status': NodeStatus.NOT_CREATED.value}

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


def get_block_device_size(device: str) -> int:
    """ Returns block device size in bytes """
    response = requests.get(
        DOCKER_LVMPY_BLOCK_SIZE_URL,
        json={'Name': None}
    )
    data = response.json()
    if data['Err'] != '':
        err = data['Err']
        logger.info(f'Lvmpy returned an error {err}')
        return -1
    return data['Size']


def get_attached_storage_block_device():
    with open(DISK_MOUNTPOINT_FILEPATH) as dm_file:
        name = dm_file.read().strip()
        return name


def get_node_hardware_info() -> dict:
    system_release = f'{platform.system()}-{platform.release()}'
    uname_version = platform.uname().version
    attached_device = get_attached_storage_block_device()
    attached_storage_size = get_block_device_size(attached_device)
    return {
        'cpu_total_cores': psutil.cpu_count(logical=True),
        'cpu_physical_cores': psutil.cpu_count(logical=False),
        'memory': psutil.virtual_memory().total,
        'swap': psutil.swap_memory().total,
        'mem_used': psutil.virtual_memory().used,
        'mem_available': psutil.virtual_memory().available,
        'system_release': system_release,
        'uname_version': uname_version,
        'attached_storage_size': attached_storage_size
    }


def get_meta_info() -> dict:
    return read_json(META_FILEPATH)


def get_skale_node_version():
    return get_meta_info()['config_stream']
