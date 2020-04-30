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
from enum import Enum


from tools.str_formatters import arguments_list_string
from tools.wallet_utils import check_required_balance

from skale.dataclasses.tx_res import TransactionFailedError
from skale.utils.helper import ip_from_bytes
from skale.wallets.web3_wallet import public_key_to_address

from core.filebeat import run_filebeat_service

logger = logging.getLogger(__name__)


class NodeStatuses(Enum):
    """This class contains possible node statuses"""
    NOT_CREATED = 0
    REQUESTED = 1
    CREATED = 2
    ERROR = 3


class Node:
    """This class contains node registration logic"""
    def __init__(self, skale, config):
        self.skale = skale
        self.config = config

    def register(self, ip, public_ip, port, name):
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
            tx_res = self.skale.manager.create_node(ip, int(port), name, public_ip,
                                                    wait_for=True,
                                                    raise_for_status=False)
            tx_res.raise_for_status()
        except TransactionFailedError:
            logger.error(arguments_list_string(
                {'tx': tx_res.hash},
                'Node creation failed',
                'error'
            ))
            return {'status': 0, 'errors': [str(tx_res.receipt)]}
        self._log_node_info('Node successfully created', ip, public_ip, port, name)
        self.config.id = self.skale.nodes_data.node_name_to_index(name)
        run_filebeat_service(public_ip, self.config.id, self.skale)
        return {'status': 1, 'data': self.config.all()}

    def _insufficient_funds(self):
        err_msg = f'Insufficient funds, re-check your wallet'
        logger.error(err_msg)
        return {'status': 0, 'errors': [err_msg]}

    def _node_already_exist(self):
        err_msg = f'Node is already installed on this machine. Node ID: {self.config.id}'
        logger.error(err_msg)
        return {'status': 0, 'errors': [err_msg]}

    def _log_node_info(self, title, ip, public_ip, port, name):
        log_params = {'IP': ip, 'Public IP': public_ip, 'Port': port, 'Name': name}
        logger.info(arguments_list_string(log_params, title))

    @property
    def info(self):
        _id = self.config.id
        if _id is not None:
            raw_info = self.skale.nodes_data.get(_id)
            return self._transform_node_info(raw_info, _id)
        return {'status': NodeStatuses.NOT_CREATED.value}

    def _transform_node_info(self, node_info, node_id):
        node_info['ip'] = ip_from_bytes(node_info['ip'])
        node_info['publicIP'] = ip_from_bytes(node_info['publicIP'])
        node_info['status'] = NodeStatuses.CREATED.value
        node_info['id'] = node_id
        node_info['publicKey'] = self.skale.web3.toHex(node_info['publicKey'])
        node_info['owner'] = public_key_to_address(node_info['publicKey'])
        return node_info
