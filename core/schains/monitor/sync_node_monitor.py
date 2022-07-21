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
from core.schains.volume import ensure_data_dir_path
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)


class SyncNodeMonitor(BaseMonitor):
    """
    SyncNodeMonitor is executed only on the sync node.
    """

    @BaseMonitor.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            ensure_data_dir_path(self.schain)
        else:
            logger.info(f'{self.p} volume - ok')
        return initial_status

    def run(self):
        logger.info(arguments_list_string({
           'sChain name': self.name
        }, 'Monitoring sync node'))
        self.config_dir()
        self.config()
        self.volume()
        self.firewall_rules()
        self.skaled_container()
