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
from abc import abstractmethod
from typing import cast

from skale import SkaleIma, SkaleManager
from skale.types.schain import SchainHash, SchainStructure

from core.checks.schain import ConfigChecks
from core.manager_cache import ManagerCache
from core.monitor.monitor_base import IMonitor
from core.monitor.schain.action_config import ConfigActionManager
from core.node import get_current_nodes
from core.node_config import NodeConfig
from core.schains.external_config import ExternalConfig, ExternalState
from tools.helper import is_passive, no_hyphens
from tools.resources import get_statsd_client
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


def run_config_pipeline(
    schain: SchainStructure,
    skale: SkaleManager,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    stream_version: str,
    manager_cache: ManagerCache,
) -> None:
    logger.info('Running config pipeline')

    logger.debug(
        arguments_list_string(
            {
                'http_posts': skale.stats.http_posts,
                'rpc_objects': skale.stats.rpc_objects,
                'most_common': skale.stats.by_method.most_common(10),
            },
            'stats_run_config_pipeline_start',
        )
    )

    rotation_data = skale.node_rotation.get_rotation(schain.name)
    ima_linked = not is_passive() and skale_ima.linker.has_schain(schain.name)
    group_index = skale.schains.name_to_group_id(schain.name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(cast(SchainHash, group_index))
    current_nodes = get_current_nodes(skale, schain.schain_hash, manager_cache)

    logger.debug(
        arguments_list_string(
            {
                'http_posts': skale.stats.http_posts,
                'rpc_objects': skale.stats.rpc_objects,
                'most_common': skale.stats.by_method.most_common(10),
            },
            'stats_run_config_pipeline_current_nodes',
        )
    )

    logger.debug('Initializing schain record')
    schain_record = SChainRecord.get_by_name(schain.name)

    estate = ExternalState(
        ima_linked=ima_linked,
        chain_id=skale_ima.web3.eth.chain_id,
        ranges=manager_cache.sync_ranges,
    )
    econfig = ExternalConfig(schain.name)
    logger.debug('Initializing config checks')
    config_checks = ConfigChecks(
        schain_name=schain.name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data.rotation_counter,
        current_nodes=current_nodes,
        last_dkg_successful=last_dkg_successful,
        econfig=econfig,
        estate=estate,
    )

    logger.debug('Initializing config action manager')
    config_am = ConfigActionManager(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=stream_version,
        checks=config_checks,
        current_nodes=current_nodes,
        estate=estate,
        econfig=econfig,
    )

    logger.debug('Gathering config status')
    checks_res = config_checks.get_all(log=False, expose=True)

    if is_passive():
        logger.info(
            'Sync node last_dkg_successful %s, rotation_data %s', last_dkg_successful, rotation_data
        )
        mon = SyncConfigMonitor(config_am, config_checks)
    else:
        mon = RegularConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(schain.name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(schain.name)}',
        rotation_data.rotation_counter,
    )

    logger.info(
        arguments_list_string(
            {
                'type': mon.__class__.__name__,
                'checks_res': checks_res,
                'rotation_data': rotation_data,
                'estate': estate.to_dict(),
            },
            'config_pipeline_info',
            'secondary',
        )
    )

    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(schain.name)}'):
        mon.run()

    logger.debug(
        arguments_list_string(
            {
                'http_posts': skale.stats.http_posts,
                'rpc_objects': skale.stats.rpc_objects,
                'most_common': skale.stats.by_method.most_common(10),
            },
            'stats_run_config_pipeline_end',
        )
    )


class BaseConfigMonitor(IMonitor):
    def __init__(self, action_manager: ConfigActionManager, checks: ConfigChecks) -> None:
        self.am = action_manager
        self.checks = checks

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info(
            arguments_list_string(
                {'type': typename, 'chain': self.am.schain.name},
                'run_config_monitor',
                'primary',
            )
        )
        try:
            self.am._upd_last_seen()
            self.execute()
            self.am.log_executed_blocks()
            self.am._upd_last_seen()
        except Exception as e:
            logger.info('Config monitor type failed %s', typename, exc_info=e)
        finally:
            logger.info('Config monitor type finished %s', typename)


class RegularConfigMonitor(BaseConfigMonitor):
    def execute(self) -> None:
        if not self.checks.config_dir:
            self.am.config_dir()
        if not self.checks.dkg:
            self.am.dkg()
        if not self.checks.external_state:
            self.am.external_state()
        if not self.checks.upstream_config:
            self.am.upstream_config()
        self.am.update_reload_ts(self.checks.skaled_node_ips)
        self.am.reset_config_record()


class SyncConfigMonitor(BaseConfigMonitor):
    def execute(self) -> None:
        if not self.checks.config_dir:
            self.am.config_dir()
        if not self.checks.external_state:
            self.am.external_state()
        if self.checks.last_dkg_successful and not self.checks.upstream_config:
            self.am.upstream_config()
            self.am.update_reload_ts(self.checks.skaled_node_ips, passive_node=True)
        self.am.reset_config_record()
