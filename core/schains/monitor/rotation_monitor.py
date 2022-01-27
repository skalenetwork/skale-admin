#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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

from core.schains.monitor.base_monitor import BaseMonitor
from core.schains.rotation import set_rotation_for_schain

logger = logging.getLogger(__name__)


class RotationMonitor(BaseMonitor):
    """
    RotationMonitor could be executed for the sChain when rotation is in progress for this chain.
    In this monitor mode there are 3 possible sub-modes:

    1. New node - when current node was added to the existing group
    2. Leaving node - when current node was removed from the existing group
    3. Staying node - when current node staying in the group
    """

    def _is_new_rotation_node(self):
        return self.rotation_data['new_node'] == self.node_config.id

    def _is_new_node(self) -> bool:
        """
        New node monitor runs in 2 cases during rotation:
        1. When the current node is marked as a new node
        2. When the current node doesn't have SKALE chain config file created
        """
        return self._is_new_rotation_node() or not self.checks.config.status

    def _is_leaving_node(self) -> bool:
        return self.rotation_data['leaving_node'] == self.node_config.id

    def rotation_request(self) -> None:
        set_rotation_for_schain(self.name, self.rotation_data['finish_ts'])

    def new_node(self) -> None:
        self.config_dir()
        self.dkg()
        self.config()
        self.volume()
        self.firewall_rules()
        self.skaled_container(sync=True)
        self.ima_container()

    def leaving_node(self) -> None:
        self.firewall_rules()
        self.skaled_container()
        self.skaled_rpc()
        self.ima_container()
        self.rotation_request()

    def staying_node(self) -> None:
        self.firewall_rules()
        self.skaled_container()
        self.skaled_rpc()
        self.ima_container()
        self.dkg()
        self.rotation_request()

    def get_rotation_mode_func(self):
        if self._is_leaving_node():
            return self.leaving_node
        if self._is_new_node():
            return self.new_node
        return self.staying_node

    @BaseMonitor.monitor_runner
    def run(self):
        rotation_mode_func = self.get_rotation_mode_func()
        logger.info(
            f'sChain: {self.name} running {type(self).__name__} '
            f'type: {rotation_mode_func}'
        )
        return rotation_mode_func()
