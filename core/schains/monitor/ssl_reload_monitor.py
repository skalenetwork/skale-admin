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

from core.schains.monitor import BaseMonitor, RegularMonitor
from core.schains.runner import restart_container
from tools.configs.containers import SCHAIN_CONTAINER

logger = logging.getLogger(__name__)


class SSLReloadMonitor(RegularMonitor):
    """
    SSLReloadMonitor is executed when new ssl certificates were uploaded
    """
    @BaseMonitor.monitor_runner
    def run(self):
        logger.info(
            '%s. Restart requested. Going to restart sChain container',
            self.p
        )
        restart_container(SCHAIN_CONTAINER, self.schain)
        record = self.schain_record
        record.set_restart_count(0)
        record.set_failed_rpc_count(0)
        record.set_needs_reload(False)
        super().run()
