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

import os
import logging

from core.schains.config.directory import skaled_status_filepath
from tools.config_utils import config_getter
from tools.helper import read_json

logger = logging.getLogger(__name__)


class SkaledStatus:
    def __init__(self, filepath: str):
        self.filepath = filepath

    @property
    @config_getter
    def subsystem_running(self) -> dict:
        return 'subsystemRunning', self.filepath

    @property
    @config_getter
    def exit_state(self) -> dict:
        return 'exitState', self.filepath

    @property
    def is_downloading_snapshot(self):
        subsystem_running = self.subsystem_running
        if not subsystem_running:
            return
        return subsystem_running['SnapshotDownloader']

    @property
    def is_exit_time_reached(self):
        exit_state = self.exit_state
        if not exit_state:
            return
        return exit_state['ExitTimeReached']

    @property
    def all(self) -> dict:
        if not os.path.isfile(self.filepath):
            logger.warning("File %s is not found", self.filepath)
            return
        return read_json(self.filepath)


def init_skaled_status(schain_name) -> SkaledStatus:
    status_filepath = skaled_status_filepath(schain_name)
    return SkaledStatus(status_filepath)
