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
import json
import logging
from json.decoder import JSONDecodeError
from typing import Optional
from abc import ABCMeta, abstractmethod

from core.schains.config.directory import node_cli_status_filepath, skaled_status_filepath
from tools.config_utils import config_getter, log_broken_status_file
from tools.helper import read_json

logger = logging.getLogger(__name__)


class IStatus(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, filepath: str) -> None:
        pass

    @property
    @abstractmethod
    def filepath(self) -> str:
        pass

    @property
    def all(self) -> dict:
        if not os.path.isfile(self.filepath):
            logger.warning("File %s is not found", self.filepath)
            return
        try:
            return read_json(self.filepath)
        except JSONDecodeError:
            log_broken_status_file(self.filepath)
            return {}

    def log(self) -> None:
        logger.info(f'{self.__class__.__name__}: \n' + json.dumps(self.all, indent=4))


class SkaledStatus(IStatus):
    def __init__(self, filepath: str) -> None:
        """
        Read-only wrapper for skaled.status file, reads from the file each time.
        Returns dict for top-level keys, True or False for second-level keys.
        Returns None for all keys if file is not found.
        """
        self._filepath = filepath

    @property
    def filepath(self) -> str:
        return self._filepath

    @property
    @config_getter
    def subsystem_running(self) -> dict:
        return 'subsystemRunning', self.filepath

    @property
    @config_getter
    def exit_state(self) -> dict:
        return 'exitState', self.filepath

    @property
    def downloading_snapshot(self) -> bool:
        subsystem_running = self.subsystem_running
        if not subsystem_running:
            return
        return subsystem_running['SnapshotDownloader']

    @property
    def exit_time_reached(self) -> bool:
        exit_state = self.exit_state
        if not exit_state:
            return
        return exit_state['ExitTimeReached']

    @property
    def clear_data_dir(self) -> bool:
        exit_state = self.exit_state
        if not exit_state:
            return
        return exit_state['ClearDataDir']

    @property
    def start_again(self) -> bool:
        exit_state = self.exit_state
        if not exit_state:
            return
        return exit_state['StartAgain']

    @property
    def start_from_snapshot(self) -> bool:
        exit_state = self.exit_state
        if not exit_state:
            return
        return exit_state['StartFromSnapshot']


class NodeCliStatus(IStatus):
    def __init__(self, filepath: str) -> None:
        """
        Read-only wrapper for node_cli.status file, reads from the file each time.
        """
        self._filepath = filepath

    @property
    @config_getter
    def repair_ts(self) -> int:
        return 'repair_ts', self.filepath

    @property
    @config_getter
    def snapshot_from(self) -> int:
        return 'snapshot_from', self.filepath

    @property
    def filepath(self) -> str:
        return self._filepath


def init_skaled_status(schain_name: str) -> SkaledStatus:
    status_filepath = skaled_status_filepath(schain_name)
    return SkaledStatus(status_filepath)


def get_skaled_status(schain_name: str) -> Optional[SkaledStatus]:
    status_path = skaled_status_filepath(schain_name)
    if os.path.isfile(status_path):
        return SkaledStatus(status_path)
    return None


def init_node_cli_status(schain_name: str) -> SkaledStatus:
    status_filepath = node_cli_status_filepath(schain_name)
    return NodeCliStatus(status_filepath)


def get_node_cli_status(schain_name: str) -> Optional[SkaledStatus]:
    status_path = node_cli_status_filepath(schain_name)
    if os.path.isfile(status_path):
        return NodeCliStatus(status_path)
    return None
