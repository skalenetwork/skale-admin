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


class RepairMonitor(BaseMonitor):
    @BaseMonitor._monitor_runner
    def run(self):
        logger.warning(f'{self.p} going to remove container and volume!')
        self.rm_skaled_container()  # todo: implement
        self.rm_volume()  # todo: implement
        self.volume()
        self.skaled_container(sync=True)  # todo: handle sync case
        # todo: set repair mode to false here
