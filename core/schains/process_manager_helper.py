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
import signal
from datetime import datetime

import psutil


from tools.helper import check_pid


logger = logging.getLogger(__name__)

TIMEOUT_COEFFICIENT = 2.2
P_KILL_WAIT_TIMEOUT = 60


def terminate_stuck_schain_process(skale, schain_record, schain):
    """
    This function terminates the process if last_seen time is less than
    DKG timeout * TIMEOUT_COEFFICIENT
    """
    allowed_last_seen_time = _calc_allowed_last_seen_time(skale)
    if not schain_record.monitor_last_seen:
        logging.warning(f'schain: {schain.name}, monitor_last_seen is None, skipping...')
        return
    schain_monitor_last_seen = schain_record.monitor_last_seen.timestamp()
    if allowed_last_seen_time > schain_monitor_last_seen:
        logger.warning(f'schain: {schain.name}, pid {schain_record.monitor_id} last seen is \
{schain_monitor_last_seen}, while max allowed last_seen is {allowed_last_seen_time}, pid \
{schain_record.monitor_id} will be terminated now!')
        terminate_schain_process(schain_record)


def terminate_schain_process(schain_record):
    log_msg = f'schain: {schain_record.name}'
    terminate_process(schain_record.monitor_id, log_msg=log_msg)


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


def is_monitor_process_alive(monitor_id):
    """Checks that provided monitor_id is inited and alive"""
    return monitor_id != 0 and check_pid(monitor_id)


def _calc_allowed_last_seen_time(skale):
    dkg_timeout = skale.constants_holder.get_dkg_timeout()
    allowed_diff = int(dkg_timeout * TIMEOUT_COEFFICIENT)
    logger.info(f'dkg_timeout: {dkg_timeout}, TIMEOUT_COEFFICIENT: {TIMEOUT_COEFFICIENT}, \
allowed_diff: {allowed_diff}')
    return datetime.now().timestamp() - allowed_diff
