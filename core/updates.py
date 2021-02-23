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
from skale import Skale
from skale.utils.helper import ip_from_bytes

from core.node_config import NodeConfig


logger = logging.getLogger(__name__)


def soft_updates(skale: Skale, node_config: NodeConfig) -> None:
    """
    This function is triggered after each admin container restart and calls all functions that
    could be required to update existing software or config files on the machine.

    Parameters:
    skale (Skale): Instance of skale.py library
    wallet (Wallet): Instance of skale.py wallet
    node_config (NodeConfig): Instance of NodeConfig class
    """
    logger.info('Performing soft updates ...')
    update_node_config_file(skale, node_config)


def update_node_config_file(skale: Skale, node_config: NodeConfig) -> None:
    """
    - Fix for node_id field in the config file
    - Add node name field to node config
    """
    if node_config.id is not None:
        if node_config.name is None:
            node_info = skale.nodes.get(node_config.id)
            node_config.name = node_info['name']
        if node_config.ip is None:
            node_info = skale.nodes.get(node_config.id)
            node_config.ip = ip_from_bytes(node_info['ip'])
