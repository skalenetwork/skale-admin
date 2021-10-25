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
from core.schains.firewall import remove_firewall_rules
from core.schains.runner import restart_container
from tools.configs.containers import SCHAIN_CONTAINER

logger = logging.getLogger(__name__)


class PostRotationMonitor(BaseMonitor):
    """
    PostRotationMonitor be executed for the sChain on the staying node when rotation is complete.
    This type of monitor reloads skaled container.
    """
    @BaseMonitor.monitor_runner
    def run(self):
        logger.info(f'{self.p} was stopped after rotation. Going to restart')
        remove_firewall_rules(self.name)
        self.config(overwrite=True)
        self.firewall_rules(overwrite=True)
        restart_container(SCHAIN_CONTAINER, self.schain)
