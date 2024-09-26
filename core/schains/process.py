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

import json
import logging
import os
import shutil
import signal
from typing import Tuple

import pathlib
import psutil

from tools.configs.schains import SCHAINS_DIR_PATH
from tools.helper import check_pid


logger = logging.getLogger(__name__)

TIMEOUT_COEFFICIENT = 2.2
P_KILL_WAIT_TIMEOUT = 60


def is_schain_process_report_exist(schain_name: str) -> None:
    path = pathlib.Path(SCHAINS_DIR_PATH).joinpath(schain_name, ProcessReport.REPORT_FILENAME)
    return path.is_file()


def get_schain_process_info(schain_name: str) -> Tuple[int | None, int | None]:
    report = ProcessReport(schain_name)
    if not ProcessReport(schain_name).is_exist():
        return None, None
    else:
        return report.pid, report.ts


class ProcessReport:
    REPORT_FILENAME = 'process.json'

    def __init__(self, name: str) -> None:
        self.path = pathlib.Path(SCHAINS_DIR_PATH).joinpath(name, self.REPORT_FILENAME)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def is_exist(self) -> bool:
        return os.path.isfile(self.path)

    @property
    def ts(self) -> int:
        return self.read()['ts']

    @ts.setter
    def ts(self, value: int) -> None:
        report = {}
        if self.is_exist():
            report = self.read()
        report['ts'] = value
        self._save_tmp(report)
        self._move()

    @property
    def pid(self) -> int:
        return self.read()['pid']

    @pid.setter
    def pid(self, value: int) -> None:
        report = {}
        if self.is_exist():
            report = self.read()
        report['pid'] = value
        self._save_tmp(report)
        self._move()

    @property
    def _tmp_path(self) -> str:
        return self.path.with_stem('.tmp.' + self.path.stem)

    def read(self) -> dict:
        with open(self.path) as process_file:
            data = json.load(process_file)
        return data

    def _save_tmp(self, report: dict) -> None:
        with open(self._tmp_path, 'w') as tmp_file:
            json.dump(report, tmp_file)

    def _move(self) -> str:
        if os.path.isfile(self._tmp_path):
            shutil.move(self._tmp_path, self.path)

    def update(self, pid: int, ts: int) -> None:
        report = {'pid': pid, 'ts': ts}
        self._save_tmp(report=report)
        self._move()

    def cleanup(self) -> None:
        os.remove(self.path)


def terminate_process(
    pid: int,
    kill_timeout: int = P_KILL_WAIT_TIMEOUT,
    log_msg: str = ''
) -> None:
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
        logger.exception(f'{log_prefix} - termination failed!')
        return


def is_monitor_process_alive(monitor_pid: int) -> bool:
    """Checks that provided monitor_id is inited and alive"""
    return monitor_pid != 0 and check_pid(monitor_pid)
