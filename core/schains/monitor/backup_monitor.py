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


logger = logging.getLogger(__name__)


class BackupMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        self.config_dir()
        self.dkg()
        self.config()
        self.volume()
        self.firewall_rules()
        self.skaled_container(sync=True)
        self.skaled_rpc()
        self.ima_container()
