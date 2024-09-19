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
import logging
from typing import Optional
from importlib import reload

from skale import Skale, SkaleIma
from skale.contracts.manager.schains import SchainStructure
from web3._utils import request as web3_request

from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.schains.checks import ConfigChecks, get_api_checks_status, TG_ALLOWED_CHECKS, SkaledChecks
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.static_params import get_automatic_repair_option
from core.schains.firewall import get_default_rule_controller
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.monitor import get_skaled_monitor, RegularConfigMonitor, SyncConfigMonitor
from core.schains.monitor.action import ConfigActionManager, SkaledActionManager
from core.schains.monitor.pipeline import Pipeline, run_pipelines
from core.schains.process import ProcessReport
from core.schains.skaled_status import get_skaled_status
from core.node import get_current_nodes

from tools.docker_utils import DockerUtils
from tools.configs import SYNC_NODE
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from tools.notifications.messages import notify_checks
from tools.helper import is_node_part_of_chain, no_hyphens
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord, upsert_schain_record


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 20
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 40

STUCK_TIMEOUT = 60 * 60 * 2
SHUTDOWN_INTERVAL = 60 * 10

logger = logging.getLogger(__name__)


def run_config_pipeline(
    skale: Skale, skale_ima: SkaleIma, schain: dict, node_config: NodeConfig, stream_version: str
) -> None:
    name = schain.name
    schain_record = SChainRecord.get_by_name(name)
    rotation_data = skale.node_rotation.get_rotation(name)
    allowed_ranges = get_sync_agent_ranges(skale)
    ima_linked = not SYNC_NODE and skale_ima.linker.has_schain(name)
    group_index = skale.schains.name_to_group_id(name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(group_index)
    current_nodes = get_current_nodes(skale, name)

    estate = ExternalState(
        ima_linked=ima_linked, chain_id=skale_ima.web3.eth.chain_id, ranges=allowed_ranges
    )
    econfig = ExternalConfig(name)
    config_checks = ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data['rotation_id'],
        current_nodes=current_nodes,
        last_dkg_successful=last_dkg_successful,
        econfig=econfig,
        estate=estate,
    )

    config_am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=stream_version,
        checks=config_checks,
        current_nodes=current_nodes,
        estate=estate,
        econfig=econfig,
    )

    status = config_checks.get_all(log=False, expose=True)
    logger.info('Config checks: %s', status)

    if SYNC_NODE:
        logger.info(
            'Sync node last_dkg_successful %s, rotation_data %s', last_dkg_successful, rotation_data
        )
        mon = SyncConfigMonitor(config_am, config_checks)
    else:
        logger.info('Regular node mode, running config monitor')
        mon = RegularConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(name)}', rotation_data['rotation_id']
    )
    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(name)}'):
        mon.run()


def run_skaled_pipeline(
    skale: Skale, schain: SchainStructure, node_config: NodeConfig, dutils: DockerUtils
) -> None:
    name = schain.name
    schain_record = SChainRecord.get_by_name(name)
    logger.info('Record: %s', SChainRecord.to_dict(schain_record))

    dutils = dutils or DockerUtils()

    rc = get_default_rule_controller(name=name)
    skaled_checks = SkaledChecks(
        schain_name=schain.name,
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )

    skaled_status = get_skaled_status(name)

    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        econfig=ExternalConfig(name),
        dutils=dutils,
    )
    check_status = skaled_checks.get_all(log=False, expose=True)
    automatic_repair = get_automatic_repair_option()
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(name, node_config.all(), api_status)

    logger.info('Skaled check status: %s', check_status)

    logger.info('Upstream config %s', skaled_am.upstream_config_path)

    mon = get_skaled_monitor(
        action_manager=skaled_am,
        check_status=check_status,
        schain_record=schain_record,
        skaled_status=skaled_status,
        automatic_repair=automatic_repair,
    )

    statsd_client = get_statsd_client()
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(name)}'):
        mon(skaled_am, skaled_checks).run()


def start_monitor(
    skale: Skale,
    schain: dict,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    process_report: ProcessReport,
    dutils: Optional[DockerUtils] = None,
) -> bool:
    reload(web3_request)
    name = schain.name

    stream_version = get_skale_node_version()
    schain_record = upsert_schain_record(name)

    dkg_timeout = skale.constants_holder.get_dkg_timeout()
    stuck_timeout = int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    is_rotation_active = skale.node_rotation.is_rotation_active(name)

    leaving_chain = not SYNC_NODE and not is_node_part_of_chain(skale, name, node_config.id)
    if leaving_chain and not is_rotation_active:
        logger.info('Not on node (%d), finishing process', node_config.id)
        return True

    logger.info(
        'sync_config_run %s, config_version %s, stream_version %s',
        schain_record.sync_config_run,
        schain_record.config_version,
        stream_version,
    )

    statsd_client = get_statsd_client()
    monitor_last_seen_ts = schain_record.monitor_last_seen.timestamp()
    statsd_client.incr(f'admin.schain.monitor.{no_hyphens(name)}')
    statsd_client.gauge(f'admin.schain.monitor_last_seen.{no_hyphens(name)}', monitor_last_seen_ts)

    pipelines = []
    if not leaving_chain:
        logger.info('Adding config pipelines to the pool')
        pipelines.append(
            Pipeline(
                name='config',
                job=functools.partial(
                    run_config_pipeline,
                    skale=skale,
                    skale_ima=skale_ima,
                    schain=schain,
                    node_config=node_config,
                    stream_version=stream_version,
                ),
            )
        )
    if schain_record.config_version != stream_version or (
        schain_record.sync_config_run and schain_record.first_run
    ):
        ConfigFileManager(name).remove_skaled_config()
    else:
        logger.info('Adding skaled pipeline to the pool')
        pipelines.append(
            Pipeline(
                name='skaled',
                job=functools.partial(
                    run_skaled_pipeline,
                    skale=skale,
                    schain=schain,
                    node_config=node_config,
                    dutils=dutils,
                ),
            )
        )

    if len(pipelines) == 0:
        logger.warning('No pipelines to run')
        return False

    run_pipelines(pipelines=pipelines, process_report=process_report, stuck_timeout=stuck_timeout)
    return True
