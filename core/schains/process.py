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
import pathlib
import shutil
import signal
import time
from typing import Tuple

import psutil

from tools.constants.schains import SCHAINS_DIR_PATH
from tools.helper import check_pid

logger = logging.getLogger(__name__)

P_KILL_WAIT_TIMEOUT = 60


def is_schain_process_report_exist(schain_name: str) -> bool:
    path = pathlib.Path(SCHAINS_DIR_PATH).joinpath(schain_name, ProcessReport.REPORT_FILENAME)
    return path.is_file()


def get_schain_process_info(schain_name: str) -> Tuple[int | None, int]:
    report = ProcessReport(schain_name)
    if not ProcessReport(schain_name).exists():
        return None, 0
    else:
        return report.pid, report.ts


def cleanup_schains_pids() -> None:
    schains_with_dirs = os.listdir(SCHAINS_DIR_PATH)
    logger.info('Cleaning process reports for all schains: %s', schains_with_dirs)
    for schain_name in schains_with_dirs:
        report = ProcessReport(schain_name)
        if report.exists():
            report.cleanup()


class ProcessReport:
    REPORT_FILENAME = 'process.json'

    def __init__(self, name: str) -> None:
        self.path = pathlib.Path(SCHAINS_DIR_PATH).joinpath(name, self.REPORT_FILENAME)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    @property
    def ts(self) -> int:
        return self.read()['ts']

    @ts.setter
    def ts(self, value: int) -> None:
        report = {}
        if self.exists():
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
        if self.exists():
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

    def _move(self) -> None:
        if os.path.isfile(self._tmp_path):
            shutil.move(self._tmp_path, self.path)

    def update(self, pid: int, ts: int) -> None:
        report = {'pid': pid, 'ts': ts}
        self._save_tmp(report=report)
        self._move()

    def cleanup(self) -> None:
        os.remove(self.path)


def terminate_process(pid: int, kill_timeout: int = P_KILL_WAIT_TIMEOUT, log_msg: str = '') -> None:
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
        logger.warning(f'{log_prefix} - timeout expired, going to kill')
        p.kill()
        logger.info(f'{log_prefix} -  process was killed')
    except Exception:
        logger.exception(f'{log_prefix} - termination failed!')
        return


def is_monitor_process_alive(monitor_pid: int) -> bool:
    """Checks that provided monitor_id is inited and alive"""
    return monitor_pid != 0 and check_pid(monitor_pid)


def is_process_healthy(schain_name: str, allowed_diff: int) -> bool:
    pid, pts = get_schain_process_info(schain_name)
    current_ts = int(time.time())
    return pid is not None and is_monitor_process_alive(pid) and current_ts - pts < allowed_diff
