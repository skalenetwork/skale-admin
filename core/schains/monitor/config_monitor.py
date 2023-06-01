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

from core.schains.monitor.base_monitor import IMonitor
from core.schains.monitor.action import ConfigActionManager


logger = logging.getLogger(__name__)


class BaseConfigMonitor(IMonitor):
    def __init__(self, action_manager: ConfigActionManager):
        self.action_manager = action_manager

    @abstractmethod
    def run(self) -> None:
        pass


class RegularConfigMonitor(BaseConfigMonitor):
    def run(self) -> None:
        self.action_manager.config_dir()
        self.action_manager.dkg()
        self.action_manager.config()
