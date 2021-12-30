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
import random
import logging
from importlib import reload

from web3._utils import request

from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.firewall import get_default_rule_controller
from core.schains.ima import ImaData
from core.schains.monitor import (
    BaseMonitor, RegularMonitor, RepairMonitor, BackupMonitor, RotationMonitor, PostRotationMonitor
)
from core.schains.rotation import check_schain_rotated
from core.schains.firewall.utils import get_sync_agent_ranges

from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.ima import DISABLE_IMA
from tools.helper import is_chain_on_node

from web.models.schain import upsert_schain_record, SChainRecord


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 90
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 180


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
        schain_monitor_sleep = random.randint(
            MIN_SCHAIN_MONITOR_SLEEP_INTERVAL,
            MAX_SCHAIN_MONITOR_SLEEP_INTERVAL
        )
        logger.info(f'{p} monitor completed, sleeping for {schain_monitor_sleep}s...')
        time.sleep(schain_monitor_sleep)

    while True:
        try:
            logger.info(f'{p} monitor created')
            reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)

            name = schain["name"]
            dutils = dutils or DockerUtils()

            if not is_chain_on_node(skale, name, node_config.id):
                logger.warning(f'{p} NOT FOUND ON NODE ({node_config.id}), finising process...')
                return True

            ima_linked = not DISABLE_IMA and skale_ima.linker.has_schain(name)
            rotation_data = skale.node_rotation.get_rotation(name)
            rotation_in_progress = skale.node_rotation.is_rotation_in_progress(name)

            sync_agent_ranges = get_sync_agent_ranges(skale)

            rc = get_default_rule_controller(
                name=name,
                sync_agent_ranges=sync_agent_ranges
            )
            schain_record = upsert_schain_record(name)
            checks = SChainChecks(
                name,
                node_config.id,
                schain_record=schain_record,
                rule_controller=rc,
                rotation_id=rotation_data['rotation_id'],
                ima_linked=ima_linked,
                dutils=dutils
            )

            ima_data = ImaData(
                linked=ima_linked,
                chain_id=skale_ima.web3.eth.chainId
            )

            monitor_class = get_monitor_type(
                schain_record,
                checks,
                rotation_in_progress,
                dutils
            )
            monitor = monitor_class(
                skale=skale,
                ima_data=ima_data,
                schain=schain,
                node_config=node_config,
                rotation_data=rotation_data,
                checks=checks,
                rule_controller=rc
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
