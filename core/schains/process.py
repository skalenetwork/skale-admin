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
import os
import shutil
import signal
import json

import pathlib
import psutil


from tools.configs.schains import SCHAINS_DIR_PATH
from tools.helper import check_pid


logger = logging.getLogger(__name__)

TIMEOUT_COEFFICIENT = 2.2
P_KILL_WAIT_TIMEOUT = 60


def terminate_process(pid, kill_timeout=P_KILL_WAIT_TIMEOUT, log_msg=''):
    log_prefix = f'pid: {pid} - '
    if log_msg != '':
        log_prefix += f'{log_msg} - '
    if pid == 0:
        logger.warning(f'{log_prefix} - pid is 0, skipping')
        return
    try:
        logger.warning(f'{log_prefix} - going to terminate')
        p = psutil.Process(pid)
        os.kill(p.pid, signal.SIGTERM)
        p.wait(timeout=kill_timeout)
        logger.info(f'{log_prefix} was terminated')
    except psutil.NoSuchProcess:
        logger.info(f'{log_prefix} - no such process')
    except psutil.TimeoutExpired:
        logger.warning(f'{log_prefix} - timout expired, going to kill')
        p.kill()
        logger.info(f'{log_prefix} -  process was killed')
    except Exception:
        logging.exception(f'{log_prefix} - termination failed!')


def terminate_schain_process(schain_record):
    log_msg = f'schain: {schain_record.name}'
    terminate_process(schain_record.monitor_id, log_msg=log_msg)


def is_monitor_process_alive(monitor_id):
    """Checks that provided monitor_id is inited and alive"""
    return monitor_id != 0 and check_pid(monitor_id)


class ProcessReport:
    REPORT_FILENAME = 'process.json'

    def __init__(self, name: str) -> None:
        self.path = pathlib.Path.joinpath(SCHAINS_DIR_PATH, name, self.REPORT_FILENAME)

    @property
    def ts(self) -> int:
        return self.read()['ts']

    @property
    def pid(self) -> int:
        return self.read()['pid']

    @property
    def _tmp_path(self) -> str:
        path = pathlib.Path(self.path)
        return path.with_stem('.tmp.' + path.stem)

    def read(self) -> dict:
        with open(self.path) as process_file:
            data = json.load(process_file)
        return data

    def _save_tmp(self, pid: int, ts: int) -> None:
        data = {'pid': pid, 'ts': ts}
        with open(self._tmp_path, 'w') as tmp_file:
            json.dump(data, tmp_file)

    def _move(self) -> str:
        if os.path.isfile(self._tmp_path):
            shutil.move(self._tmp_path, self.path)

    def update(self, pid: int, ts: int) -> None:
        self._save_tmp(pid=pid, ts=ts)
        self._move()
