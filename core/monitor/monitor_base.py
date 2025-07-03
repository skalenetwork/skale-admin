#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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
from abc import ABC, abstractmethod

from core.checks.base import BaseSkaledChecks
from core.monitor.action_base import BaseSkaledActionManager

logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class IMonitor(ABC):
    @abstractmethod
    def run(self):
        pass


class BaseSkaledMonitor(IMonitor):
    @property
    @abstractmethod
    def am(self) -> BaseSkaledActionManager:
        pass

    @property
    @abstractmethod
    def checks(self) -> BaseSkaledChecks:
        pass

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info('Skaled monitor type starting %s', typename)
        try:
            self.am._upd_last_seen()
            self.execute()
            self.am._upd_chain_record()
            self.am.log_executed_blocks()
            self.am._upd_last_seen()
        except Exception as e:
            logger.info('Skaled monitor type failed %s', typename, exc_info=e)
        finally:
            logger.info('Skaled monitor type finished %s', typename)
