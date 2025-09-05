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

from skale import SkaleManager, SkaleIma
from skale.types.schain import SchainName, SchainHash

from core.monitor.monitor_base import IMonitor
from core.node_config import NodeConfig
from core.checks.schain import ConfigChecks
from core.firewall.utils import get_sync_agent_ranges
from core.schains.external_config import ExternalConfig, ExternalState
from core.monitor.schain.action_config import ConfigActionManager
from core.node import get_current_nodes

from tools.configs import PASSIVE_NODE
from tools.helper import no_hyphens
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord


logger = logging.getLogger(__name__)


def run_config_pipeline(
    schain_name: SchainName,
    skale: SkaleManager,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    stream_version: str,
) -> None:
    logger.info('Gathering initial skale manager data')
    schain = skale.schains.get_by_name(schain_name)
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    allowed_ranges = get_sync_agent_ranges(skale)
    ima_linked = not PASSIVE_NODE and skale_ima.linker.has_schain(schain_name)
    group_index = skale.schains.name_to_group_id(schain_name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(cast(SchainHash, group_index))
    current_nodes = get_current_nodes(skale, schain_name)

    logger.info('Initializing schain record')
    schain_record = SChainRecord.get_by_name(schain_name)

    estate = ExternalState(
        ima_linked=ima_linked, chain_id=skale_ima.web3.eth.chain_id, ranges=allowed_ranges
    )
    econfig = ExternalConfig(schain_name)
    logger.info('Initializing config checks')
    config_checks = ConfigChecks(
        schain_name=schain_name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data.rotation_counter,
        current_nodes=current_nodes,
        last_dkg_successful=last_dkg_successful,
        econfig=econfig,
        estate=estate,
    )

    logger.info('Initializing config action manager')
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

    logger.info('Gathering config status')
    status = config_checks.get_all(log=False, expose=True)
    logger.info('Config status: %s', status)

    if PASSIVE_NODE:
        logger.info(
            'Sync node last_dkg_successful %s, rotation_data %s', last_dkg_successful, rotation_data
        )
        mon = SyncConfigMonitor(config_am, config_checks)
    else:
        logger.info('Regular node mode, running config monitor')
        mon = RegularConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(schain_name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(schain_name)}',
        rotation_data.rotation_counter,
    )
    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(schain_name)}'):
        mon.run()


class BaseConfigMonitor(IMonitor):
    def __init__(self, action_manager: ConfigActionManager, checks: ConfigChecks) -> None:
        self.am = action_manager
        self.checks = checks

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info('Config monitor type starting %s', typename)
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
