#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022 SKALE Labs
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

from skale import Skale, SkaleIma

from core.schains.monitor import (
    BaseMonitor,
    SyncNodeMonitor,
    SyncNodeRotationMonitor
)
from core.schains.firewall import get_default_rule_controller

from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.ima import ImaData

from core.schains.skaled_status import init_skaled_status, SkaledStatus

from tools.str_formatters import arguments_list_string
from tools.docker_utils import DockerUtils
from tools.configs import SYNC_NODE_ROTATION_TS_DIFF

from web.models.schain import upsert_schain_record, SChainRecord


logger = logging.getLogger(__name__)


def _is_sync_rotation_mode(
    checks: SChainChecks,
    finish_ts: int
) -> bool:
    # return _is_sync_node_rotation_timeframe(finish_ts) and not checks.skaled_container.status
    if finish_ts is None:
        finish_ts = 0
    return _is_sync_node_rotation_timeframe(finish_ts)


def _is_sync_node_rotation_timeframe(finish_ts: int) -> bool:
    current_time = time.time()
    logger.info(f'Current time is {current_time}, finish_ts is {finish_ts}, rotation ts diff: \
{SYNC_NODE_ROTATION_TS_DIFF}')
    return current_time >= finish_ts and current_time < finish_ts + SYNC_NODE_ROTATION_TS_DIFF


def get_monitor_type(
        schain_record: SChainRecord,
        checks: SChainChecks,
        skaled_status: SkaledStatus,
        finish_ts: int
) -> BaseMonitor:
    # TODO: RepairMonitor for Sync node should be discussed later
    # if _is_repair_mode(schain_record, checks, skaled_status):
    #     return RepairMonitor
    if _is_sync_rotation_mode(checks, finish_ts):
        return SyncNodeRotationMonitor
    return SyncNodeMonitor


def monitor_sync_node(
    skale: Skale,
    skale_ima: SkaleIma,
    schain_name: str,
    node_config: NodeConfig,
    dutils: DockerUtils = None
):
    logger.info(arguments_list_string({
        'sChain name': schain_name
        }, 'Running sync node monitor'))

    schain = skale.schains.get_by_name(schain_name)

    rotation_data = skale.node_rotation.get_rotation(schain_name)

    rc = get_default_rule_controller(
        name=schain_name
    )

    schain_record = upsert_schain_record(schain_name)
    checks = SChainChecks(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rc,
        rotation_id=rotation_data['rotation_id'],
        ima_linked=False,
        dutils=dutils
    )

    ima_data = ImaData(
        linked=False,
        chain_id=skale_ima.web3.eth.chainId
    )

    skaled_status = init_skaled_status(schain_name)

    finish_ts = skale.node_rotation.get_schain_finish_ts(
        node_id=rotation_data['leaving_node'],
        schain_name=schain_name
    )

    monitor_class = get_monitor_type(
        schain_record,
        checks,
        skaled_status,
        finish_ts
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
