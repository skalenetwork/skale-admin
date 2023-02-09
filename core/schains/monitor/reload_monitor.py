#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022 SKALE Labs
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

from core.schains.monitor import BaseMonitor
from core.schains.ssl import update_ssl_change_date

logger = logging.getLogger(__name__)


class ReloadMonitor(BaseMonitor):
    """
    ReloadMonitor is executed when new SSL certificates were uploaded or when reload is requested.
    """
    @BaseMonitor.monitor_runner
    def run(self):
        logger.info(
            '%s. Reload requested. Going to restart sChain container',
            self.p
        )
        self.reloaded_skaled_container()
        record = self.schain_record
        record.set_restart_count(0)
        record.set_failed_rpc_count(0)
        update_ssl_change_date(record)
        record.set_needs_reload(False)
