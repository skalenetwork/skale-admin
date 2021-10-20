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
from tools.notifications.messages import notify_repair_mode

logger = logging.getLogger(__name__)


class RepairMonitor(BaseMonitor):
    """
    RepairMonitor could be executed for the sChain in 2 cases:
    1. Repair mode was toggled by node owner manually
    2. Wrong exit code on skaled container (currently only 200 exit code is handled)

    In this mode container and volume are removed and replaced with a new ones, in a sync mode.
    """

    def notify_repair_mode(self) -> None:
        notify_repair_mode(
            self.node_config.all(),
            self.name
        )

    def disable_repair_mode(self) -> None:
        self.schain_record.set_repair_mode(False)

    @BaseMonitor._monitor_runner
    def run(self):
        logger.warning(f'REPAIR MODE was toggled - \
repair_mode: {self.schain_record.repair_mode}, exit_code_ok: {self.checks.exit_code_ok}')
        self.notify_repair_mode()
        self.cleanup_schain_docker_entity()
        self.volume()
        self.skaled_container(sync=True)  # todo: handle sync case
        self.skaled_rpc()
        self.disable_repair_mode()
