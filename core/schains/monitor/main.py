#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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

import time
import logging
from importlib import reload

from web3._utils import request

from core.node_config import NodeConfig
from core.schains.monitor import (
    BaseMonitor, RegularMonitor, RepairMonitor, BackupMonitor, RotationMonitor
)
from core.schains.checks import SChainChecks

from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN

from web.models.schain import upsert_schain_record, SChainRecord


logger = logging.getLogger(__name__)


def get_log_prefix(name):
    return f'schain: {name} -'


def _is_backup_mode(schain_record):
    return schain_record.first_run and not schain_record.new_schain and BACKUP_RUN


def _is_repair_mode(schain_record, checks):
    return schain_record.repair_mode or not checks.exit_code_ok


def _is_rotation_mode():
    return False  # todo!


def get_monitor_type(schain_record: SChainRecord, checks: SChainChecks) -> BaseMonitor:
    if _is_backup_mode(schain_record):
        return BackupMonitor
    if _is_repair_mode(schain_record, checks):
        return RepairMonitor
    if _is_rotation_mode():
        return RotationMonitor
    return RegularMonitor


def run_monitor_for_schain(skale, skale_ima, node_config: NodeConfig, schain):
    p = get_log_prefix(schain["name"])
    try:
        logger.info(f'{p} monitor created')
        reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)

        name = schain["name"]
        dutils = DockerUtils()

        while True:
            ima_linked = skale_ima.linker.has_schain(name)
            rotation_id = skale.schains.get_last_rotation_id(name)

            schain_record = upsert_schain_record(name)
            checks = SChainChecks(
                name,
                node_config.id,
                schain_record=schain_record,
                rotation_id=rotation_id,
                ima_linked=ima_linked,
                dutils=dutils
            )

            monitor_class = get_monitor_type()
            monitor = monitor_class(
                skale=skale,
                schain=schain,
                node_config=node_config,
                rotation_id=rotation_id,
                checks=checks
            )
            monitor.run()
            time.sleep(30)  # todo: change sleep interval

    except Exception:
        logger.exception(f'{p} monitor failed')
