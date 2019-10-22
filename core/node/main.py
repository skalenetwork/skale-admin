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

import docker, logging

from core.schains.monitor import SchainsMonitor
from core.schains.cleaner import SChainsCleaner
from core.node.statuses import NodeStatuses
from core.filebeat import run_filebeat_service

from tools.str_formatters import arguments_list_string

import skale.utils.helper as Helper

docker_client = docker.from_env()
logger = logging.getLogger(__name__)


class Node:
    def __init__(self, skale, config, wallet):
        self.skale = skale
        self.wallet = wallet
        self.config = config

        node_id = self.get_node_id()
        if node_id is not None:
            self.run_schains_monitor(node_id)

        self.install_nonce = None
        self.install_address = None

    def run_schains_monitor(self, node_id):
        self.schains_monitor = SchainsMonitor(self.skale, self.wallet, node_id)
        self.schains_cleaner = SChainsCleaner(self.skale, node_id)

    def create(self, ip, public_ip, port, name):
        log_params = {'IP': ip, 'Public IP': public_ip, 'Port': port, 'Name': name}
        logger.info(arguments_list_string(log_params, 'Node create started'))

        node_id = self.get_node_id()
        if node_id:
            err_msg = f'Node is already installed on this machine. Node ID: {node_id}'
            logger.error(err_msg)
            return {'status': 0, 'errors': [err_msg]}

        if not self.wallet.check_required_balance():
            wallet = self.wallet.get_with_balance()
            required_balances = self.wallet.get_required_balance()
            err_msg = f'Balance is too low to create a node: {wallet["eth_balance"]} ETH, {wallet["skale_balance"]} SKALE'
            required_balance_msg = f'Required amount: {required_balances["eth_balance"]} ETH, {required_balances["skale_balance"]} SKALE'
            logger.error(err_msg)
            logger.error(required_balance_msg)
            return {'status': 0, 'errors': [err_msg, required_balance_msg]}

        local_wallet = self.wallet.get_full()
        res = self.skale.manager.create_node(ip, int(port), name, local_wallet, public_ip)
        logger.info(f'create_node res: {res}')

        self.install_nonce = res['nonce']
        self.install_address = local_wallet['address']
        receipt = Helper.await_receipt(self.skale.web3, res[
            'tx'])  # todo: return tx and wait for the receipt in async mode


        if receipt['status'] != 1:
            err_msg = f'Transaction failed. TX: {res["tx"]}' # todo: convert to hex
            logger.error(arguments_list_string({'tx': res["tx"]}, 'Node creation failed', 'error'))
            logger.error(f'create_node receipt: {receipt}')
            return {'status': 0, 'errors': [err_msg]}

        logger.info(arguments_list_string(log_params, 'Node successfully created', 'success'))

        node_id = self.skale.nodes_data.node_name_to_index(name)
        self.config.update({'node_id': node_id})
        self.run_schains_monitor(node_id)
        run_filebeat_service(public_ip, node_id, self.skale)
        return {'status': 1, 'data': self.config.get()}

    def get_node_id(self):
        try:
            return self.config['node_id']
        except KeyError:
            logger.debug('get_node_id: No node installed on this machine.')
            return None

    def get_node_info(self):
        node_id = self.get_node_id()
        if node_id is not None:
            node_info = self.skale.nodes_data.get(node_id)
            if not node_info: return {'status': NodeStatuses.ERROR.value}
            return self.transform_node_info(node_info, node_id)
        else:
            return {'status': NodeStatuses.NOT_CREATED.value}

    def transform_node_info(self, node_info, node_id):
        node_info['ip'] = Helper.ip_from_bytes(node_info['ip'])
        node_info['publicIP'] = Helper.ip_from_bytes(node_info['publicIP'])
        node_info['status'] = NodeStatuses.CREATED.value
        node_info['id'] = node_id
        node_info['publicKey'] = self.skale.web3.toHex(node_info['publicKey'])
        node_info['owner'] = Helper.public_key_to_address(node_info['publicKey'])
        return node_info