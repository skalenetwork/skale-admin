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
    BaseMonitor, RegularMonitor, RepairMonitor, BackupMonitor, RotationMonitor, PostRotationMonitor
)
from core.schains.ima import ImaData
from core.schains.checks import SChainChecks
from core.schains.rotation import check_schain_rotated
from core.schains.utils import get_sync_agent_ranges

from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN

from web.models.schain import upsert_schain_record, SChainRecord


SCHAIN_MONITOR_SLEEP_INTERVAL = 60
# SCHAIN_MONITOR_SLEEP_INTERVAL = 500 TODO

logger = logging.getLogger(__name__)


def get_log_prefix(name):
    return f'schain: {name} -'


def _is_backup_mode(schain_record: SChainRecord) -> bool:
    return schain_record.first_run and not schain_record.new_schain and BACKUP_RUN


def _is_repair_mode(schain_record: SChainRecord, checks: SChainChecks) -> bool:
    return schain_record.repair_mode or not checks.exit_code_ok.status


def _is_rotation_mode(rotation_in_progress: bool) -> bool:
    return rotation_in_progress


def _is_post_rotation_mode(schain_name: str, dutils=None) -> bool:
    return check_schain_rotated(schain_name, dutils)


def get_monitor_type(
        schain_record: SChainRecord,
        checks: SChainChecks,
        rotation_in_progress: bool,
        dutils=None
        ) -> BaseMonitor:
    if _is_backup_mode(schain_record):
        return BackupMonitor
    if _is_repair_mode(schain_record, checks):
        return RepairMonitor
    if _is_rotation_mode(rotation_in_progress):
        return RotationMonitor
    if _is_post_rotation_mode(checks.name, dutils=dutils):
        return PostRotationMonitor
    return RegularMonitor


def run_monitor_for_schain(skale, skale_ima, node_config: NodeConfig, schain, dutils=None,
                           once=False):
    p = get_log_prefix(schain["name"])

    def post_monitor_sleep():
        logger.info(f'{p} monitor completed, sleeping for {SCHAIN_MONITOR_SLEEP_INTERVAL}s...')
        time.sleep(SCHAIN_MONITOR_SLEEP_INTERVAL)

    while True:
        try:
            logger.info(f'{p} monitor created')
            reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)

            name = schain["name"]
            dutils = dutils or DockerUtils()

            ima_linked = skale_ima.linker.has_schain(name)
            rotation_data = skale.node_rotation.get_rotation(name)
            rotation_in_progress = skale.node_rotation.is_rotation_in_progress(name)

            sync_agent_ranges = get_sync_agent_ranges(skale)

            schain_record = upsert_schain_record(name)
            checks = SChainChecks(
                name,
                node_config.id,
                schain_record=schain_record,
                rotation_id=rotation_data['rotation_id'],
                ima_linked=ima_linked,
                sync_agent_ranges=sync_agent_ranges,
                dutils=dutils
            )

            ima_data = ImaData(
                linked=skale_ima.linker.has_schain(name),
                chain_id=skale_ima.web3.eth.chainId
            )

            monitor_class = get_monitor_type(schain_record, checks, rotation_in_progress, dutils)
            monitor = monitor_class(
                skale=skale,
                ima_data=ima_data,
                schain=schain,
                node_config=node_config,
                rotation_data=rotation_data,
                checks=checks,
                sync_agent_ranges=sync_agent_ranges
            )
            monitor.run()
            if once:
                return True
            post_monitor_sleep()
        except Exception:
            logger.exception(f'{p} monitor failed')
            if once:
                return False
            post_monitor_sleep()
