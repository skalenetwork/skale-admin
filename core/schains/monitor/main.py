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

import functools
import time
import random
import logging
from typing import Dict

from skale import Skale, SkaleIma

from core.node_config import NodeConfig
from core.schains.checks import ConfigChecks, SkaledChecks, SChainChecks
from core.schains.firewall import get_default_rule_controller
from core.schains.ima import ImaData
from core.schains.monitor import (
    BaseMonitor,
    BackupMonitor,
    PostRotationMonitor,
    RegularMonitor,
    RepairMonitor,
    RotationMonitor,
    ReloadMonitor
)
from core.schains.monitor.config_monitor import RegularConfigMonitor
from core.schains.monitor.skaled_monitor import RegularSkaledMonitor
from core.schains.monitor.action import ConfigActionManager, SkaledActionManager
from core.schains.task import run_tasks, Task
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.skaled_status import SkaledStatus

from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.ima import DISABLE_IMA

from web.models.schain import upsert_schain_record, SChainRecord


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 90
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 180


logger = logging.getLogger(__name__)


def get_log_prefix(name):
    return f'schain: {name} -'


def _is_backup_mode(schain_record: SChainRecord) -> bool:
    return schain_record.first_run and not schain_record.new_schain and BACKUP_RUN


def _is_repair_mode(
    schain_record: SChainRecord,
    checks: SChainChecks,
    skaled_status: SkaledStatus
) -> bool:
    return schain_record.repair_mode or _is_skaled_repair_status(checks, skaled_status)


def _is_rotation_mode(is_rotation_active: bool) -> bool:
    return is_rotation_active


def _is_post_rotation_mode(checks: SChainChecks, skaled_status: SkaledStatus) -> bool:
    skaled_status.log()
    return not checks.skaled_container.status and skaled_status.exit_time_reached


def _is_reload_mode(schain_record: SChainRecord) -> bool:
    return schain_record.needs_reload


def _is_skaled_repair_status(checks: SChainChecks, skaled_status: SkaledStatus) -> bool:
    skaled_status.log()
    needs_repair = skaled_status.clear_data_dir and skaled_status.start_from_snapshot
    return not checks.skaled_container.status and needs_repair


def _is_skaled_reload_status(checks: SChainChecks, skaled_status: SkaledStatus) -> bool:
    skaled_status.log()
    needs_reload = skaled_status.start_again and not skaled_status.start_from_snapshot
    return not checks.skaled_container.status and needs_reload


def get_monitor_type(
        schain_record: SChainRecord,
        checks: SChainChecks,
        is_rotation_active: bool,
        skaled_status: SkaledStatus
        ) -> BaseMonitor:
    if _is_backup_mode(schain_record):
        return BackupMonitor
    if _is_repair_mode(schain_record, checks, skaled_status):
        return RepairMonitor
    if _is_rotation_mode(is_rotation_active):
        return RotationMonitor
    if _is_post_rotation_mode(checks, skaled_status):
        return PostRotationMonitor
    if _is_reload_mode(schain_record):
        return ReloadMonitor
    return RegularMonitor


def monitor_config(skale: Skale, schain: Dict, node_config: NodeConfig) -> None:
    name = schain['name']
    schain_record = upsert_schain_record(name)
    rotation_data = skale.node_rotation.get_rotation(name)
    config_checks = ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        rotation_id=rotation_data['rotation_id']
    )

    config_am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        checks=config_checks
    )

    mon = RegularConfigMonitor(config_am)
    mon.run()


def monitor_containers(
    skale: Skale,
    skale_ima: SkaleIma,
    schain: Dict,
    dutils: DockerUtils
) -> None:
    name = schain['name']
    schain_record = upsert_schain_record(name)

    dutils = dutils or DockerUtils()

    rotation_data = skale.node_rotation.get_rotation(name)
    ima_linked = not DISABLE_IMA and skale_ima.linker.has_schain(name)

    sync_agent_ranges = get_sync_agent_ranges(skale)

    rc = get_default_rule_controller(
        name=name,
        sync_agent_ranges=sync_agent_ranges
    )
    skaled_checks = SkaledChecks(
        schain_name=schain['name'],
        schain_record=schain_record,
        rule_controller=rc,
        ima_linked=ima_linked,
        dutils=dutils
    )

    finish_ts = skale.node_rotation.get_schain_finish_ts(
      node_id=rotation_data['leaving_node'],
      schain_name=name
    )

    ima_data = ImaData(
        linked=ima_linked,
        chain_id=skale_ima.web3.eth.chainId
    )

    # finish ts can be fetched from config
    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        ima_data=ima_data,
        checks=skaled_checks,
        finish_ts=finish_ts,
        dutils=dutils
    )

    mon = RegularSkaledMonitor(skaled_am)
    mon.run()


def run_monitor_for_schain(
    skale,
    skale_ima,
    node_config: NodeConfig,
    schain,
    dutils=None,
    once=False
):
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
            name = schain["name"]
            tasks = [
                Task(
                    f'{name}-config',
                    functools.partial(
                        monitor_config,
                        skale=skale,
                        schain=schain,
                        node_config=node_config
                    )
                ),
                Task(
                    f'{name}-skaled',
                    functools.partial(
                        monitor_containers,
                        skale=skale,
                        skale_ima=skale_ima,
                        schain=schain,
                        dutils=dutils
                    ),
                )
            ]
            run_tasks(name=name, tasks=tasks)
            # logger.info(f'{p} monitor created')
            # reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)

            # dutils = dutils or DockerUtils()

            # is_rotation_active = skale.node_rotation.is_rotation_active(name)

            # if not is_node_part_of_chain(skale, name, node_config.id) and not is_rotation_active:
            #     logger.warning(f'{p} NOT ON NODE ({node_config.id}), finising process...')
            #     return True

            # ima_linked = not DISABLE_IMA and skale_ima.linker.has_schain(name)
            # rotation_data = skale.node_rotation.get_rotation(name)

            # sync_agent_ranges = get_sync_agent_ranges(skale)

            # rc = get_default_rule_controller(
            #     name=name,
            #     sync_agent_ranges=sync_agent_ranges
            # )
            # schain_record = upsert_schain_record(name)
            # checks = SChainChecks(
            #     name,
            #     node_config.id,
            #     schain_record=schain_record,
            #     rule_controller=rc,
            #     rotation_id=rotation_data['rotation_id'],
            #     ima_linked=ima_linked,
            #     dutils=dutils
            # )

            # ima_data = ImaData(
            #     linked=ima_linked,
            #     chain_id=skale_ima.web3.eth.chainId
            # )
            # skaled_status = init_skaled_status(name)

            # monitor_class = get_monitor_type(
            #     schain_record,
            #     checks,
            #     is_rotation_active,
            #     skaled_status
            # )
            # monitor = monitor_class(
            #     skale=skale,
            #     ima_data=ima_data,
            #     schain=schain,
            #     node_config=node_config,
            #     rotation_data=rotation_data,
            #     checks=checks,
            #     rule_controller=rc
            # )
            # monitor.run()
            # if once:
            #     return True
            post_monitor_sleep()
        except Exception:
            logger.exception(f'{p} monitor failed')
            if once:
                return False
            post_monitor_sleep()
