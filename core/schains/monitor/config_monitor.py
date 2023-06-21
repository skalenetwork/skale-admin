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
from abc import abstractmethod

from core.schains.checks import ConfigChecks
from core.schains.monitor.base_monitor import IMonitor
from core.schains.monitor.action import ConfigActionManager


logger = logging.getLogger(__name__)


class BaseConfigMonitor(IMonitor):
    def __init__(
        self,
        action_manager: ConfigActionManager,
        checks: ConfigChecks
    ) -> None:
        self.am = action_manager
        self.checks = checks

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info('Config monitor type %s starting', typename)
        self.am._upd_last_seen()
        self.am._upd_schain_record()
        self.execute()
        self.am.log_executed_blocks()
        self.am._upd_last_seen()
        logger.info('Config monitor type %s finished', typename)


class RegularConfigMonitor(BaseConfigMonitor):
    def execute(self) -> None:
        if not self.checks.config_dir:
            self.am.config_dir()
        if not self.checks.dkg:
            self.am.dkg()
        if not self.checks.upstream_config:
            self.am.upstream_config()
