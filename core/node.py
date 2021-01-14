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
import time
from enum import Enum

from skale.transactions.result import TransactionFailedError
from skale.utils.helper import ip_from_bytes
from skale.wallets.web3_wallet import public_key_to_address

from core.filebeat import run_filebeat_service

from tools.configs.filebeat import MONITORING_CONTAINERS
from tools.configs.resource_allocation import DISK_MOUNTPOINT_FILEPATH
from tools.configs.web3 import NODE_REGISTER_CONFIRMATION_BLOCKS
from tools.str_formatters import arguments_list_string
from tools.wallet_utils import check_required_balance

logger = logging.getLogger(__name__)


class NodeStatuses(Enum):
    """This class contains possible node statuses"""
    ACTIVE = 0
    LEAVING = 1
    FROZEN = 2
    IN_MAINTENANCE = 3
    LEFT = 4
    NOT_CREATED = 5


class NodeExitStatuses(Enum):
    """This class contains possible node exit statuses"""
    ACTIVE = 0
    IN_PROGRESS = 1
    WAIT_FOR_ROTATIONS = 2
    COMPLETED = 3


class SchainExitStatuses(Enum):
    """This class contains possible schain exit statuses"""
    ACTIVE = 0
    LEAVING = 1
    LEFT = 2


class Node:
    """This class contains node registration logic"""
    def __init__(self, skale, config):
        self.skale = skale
        self.config = config

    def register(self, ip, public_ip, port, name,
                 gas_limit=None, gas_price=None, skip_dry_run=False):
        """
        Main node registration function.

        Parameters:
        ip (str): P2P IP address that will be assigned to the node
        public_ip (str): Public IP address that will be assigned to the node
        port (int): Base port that will be used for sChains on the node
        name (str): Node name

        Returns:
        dict: Execution status and node config
        """
        self._log_node_info('Node create started', ip, public_ip, port, name)
        if self.config.id is not None:
            return self._node_already_exist()
        if not check_required_balance(self.skale):
            return self._insufficient_funds()
        try:
            self.skale.manager.create_node(
                ip=ip,
                port=int(port),
                name=name,
                public_ip=public_ip,
                gas_limit=gas_limit,
                gas_price=gas_price,
                skip_dry_run=skip_dry_run,
                wait_for=True,
                confirmation_blocks=NODE_REGISTER_CONFIRMATION_BLOCKS
            )
        except TransactionFailedError:
            logger.exception('Node creation failed')
            return {
                'status': 0,
                'errors': [
                    f'node creation failed: {ip}:{port}, name: {name}'
                ]
            }

        self._log_node_info('Node successfully created', ip,
                            public_ip, port, name)
        self.config.name = name
        self.config.id = self.skale.nodes.node_name_to_index(name)
        self.config.ip = ip
        if MONITORING_CONTAINERS:
            run_filebeat_service(public_ip, self.config.id, self.skale)
        return {'status': 1, 'data': self.config.all()}

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
                'status': SchainExitStatuses.ACTIVE.name
            }
            for schain in active_schains
        ]
        rotated_schains = self.skale.node_rotation.get_leaving_history(
            self.config.id)
        current_time = time.time()
        for schain in rotated_schains:
            if current_time > schain['finished_rotation']:
                status = SchainExitStatuses.LEFT
            else:
                status = SchainExitStatuses.LEAVING
            schain_name = self.skale.schains.get(schain['id'])['name']
            if not schain_name:
                schain_name = '[REMOVED]'
            schain_statuses.append(
                {'name': schain_name, 'status': status.name}
            )
        node_status = NodeExitStatuses(
            self.skale.nodes.get_node_status(self.config.id))
        exit_time = self.skale.nodes.get_node_finish_time(self.config.id)
        if node_status == NodeExitStatuses.WAIT_FOR_ROTATIONS and \
                current_time >= exit_time:
            node_status = NodeExitStatuses.COMPLETED
        return {'status': node_status.name, 'data': schain_statuses,
                'exit_time': exit_time}

    def set_maintenance_on(self):
        if NodeStatuses(self.info['status']) != NodeStatuses.ACTIVE:
            err_msg = 'Node should be active'
            logger.error(err_msg)
            return {'status': 1, 'errors': [err_msg]}
        try:
            self.skale.nodes.set_node_in_maintenance(self.config.id)
        except TransactionFailedError:
            err_msg = 'Moving node to maintenance mode failed'
            logger.exception(err_msg)
            return {'status': 1, 'errors': [err_msg]}
        return {'status': 0}

    def set_maintenance_off(self):
        if NodeStatuses(self.info['status']) != NodeStatuses.IN_MAINTENANCE:
            err_msg = 'Node is not in maintenance mode'
            logger.error(err_msg)
            return {'status': 1, 'errors': [err_msg]}
        try:
            self.skale.nodes.remove_node_from_in_maintenance(self.config.id)
        except TransactionFailedError:
            err_msg = 'Removing node from maintenance mode failed'
            logger.exception(err_msg)
            return {'status': 1, 'errors': [err_msg]}
        return {'status': 0}

    def _insufficient_funds(self):
        err_msg = 'Insufficient funds, re-check your wallet'
        logger.error(err_msg)
        return {'status': 0, 'errors': [err_msg]}

    def _node_already_exist(self):
        err_msg = (
            f'Node is already installed on this machine. '
            f'Node ID: {self.config.id}'
        )
        logger.error(err_msg)
        return {'status': 0, 'errors': [err_msg]}

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
        return {'status': NodeStatuses.NOT_CREATED.value}

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
    status = NodeStatuses(node_info['status'])
    if status == NodeStatuses.FROZEN and finish_time < time.time():
        return NodeStatuses.LEFT.value
    return status.value


def get_block_device_size(device: str) -> int:
    """ Returns block device size in bytes """
    with open(f'/sys/block/{device}/size') as sys_stats:
        return int(sys_stats.read()) // 2


def get_attached_storage_block_device():
    with open(DISK_MOUNTPOINT_FILEPATH) as dm_file:
        full_name = dm_file.read().strip()
        name = full_name[4:]  # remove /dev prefix
        return name


def get_node_hardware_info() -> dict:
    system_release = f'{platform.system()}-{platform.release()}'
    uname_version = platform.uname().version
    attached_device = get_attached_storage_block_device()
    attached_storage_size = get_block_device_size(attached_device)
    return {
        'CPU': psutil.cpu_count(logical=False),
        'memory': psutil.virtual_memory().total,
        'swap': psutil.swap_memory().total,
        'system_release': system_release,
        'uname_version': uname_version,
        'attached_storage_size': attached_storage_size
    }
