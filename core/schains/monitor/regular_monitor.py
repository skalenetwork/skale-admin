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

from skale.schain_config.generator import get_nodes_for_schain

from core.schains.monitor.base_monitor import BaseMonitor, ConfigStatus
from core.schains.monitor.containers import get_restart_slot_ts, set_exit_ts


logger = logging.getLogger(__name__)


class RegularMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        self.config_dir()
        self.dkg()
        if self.config() == ConfigStatus.NEEDS_RELOAD:
            exit_ts = get_restart_slot_ts(
                get_nodes_for_schain(self.skale, self.name),
                self.node_config.id
            )
            set_exit_ts(self.name, exit_ts)
        self.volume()
        self.firewall_rules()
        self.skaled_container()
        self.skaled_rpc()
        self.ima_container()
