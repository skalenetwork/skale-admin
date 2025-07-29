#   -*- coding: utf-8 -*-
#
#  This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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
from typing import Optional, List

from skale import SkaleManager, SkaleIma
from skale.types.rotation import Rotation
from skale.types.schain import Schain

from core.checks.base import CheckRes
from core.monitor.action_base import BaseActionManager
from core.node_config import NodeConfig
from core.node import ExtendedManagerNodeInfo, calc_reload_ts, get_node_index_in_group
from core.checks.schain import ConfigChecks
from core.dkg.schain import (
    DkgError,
    get_dkg_client,
    get_secret_key_share_filepath,
    run_dkg,
    save_dkg_results,
)

from core.config.schain.directory import init_schain_config_dir
from core.config.schain.main import create_new_upstream_config, update_schain_config_version
from core.config.schain.file_manager import ConfigFileManager

from core.schains.external_config import ExternalConfig, ExternalState

from tools.configs import SYNC_NODE
from tools.helper import no_hyphens
from tools.node_options import NodeOptions
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord, upsert_schain_record


logger = logging.getLogger(__name__)


class ConfigActionManager(BaseActionManager):
    def __init__(
        self,
        skale: SkaleManager,
        skale_ima: SkaleIma,
        schain: Schain,
        node_config: NodeConfig,
        rotation_data: Rotation,
        stream_version: str,
        checks: ConfigChecks,
        estate: ExternalState,
        current_nodes: List[ExtendedManagerNodeInfo],
        econfig: Optional[ExternalConfig] = None,
        node_options: NodeOptions | None = None,
    ):
        self.skale = skale
        self.skale_ima = skale_ima
        self.schain = schain
        self.generation = schain.generation
        self.node_config = node_config
        self.checks = checks
        self.stream_version = stream_version
        self.current_nodes = current_nodes

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data.rotation_counter
        self.estate = estate
        self.econfig = econfig or ExternalConfig(name=schain.name)
        self.node_options = node_options or NodeOptions()
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=self.schain.name)
        self.statsd_client = get_statsd_client()
        super().__init__(name=schain.name)
        self.name = schain.name

    @property
    def chain_record(self) -> SChainRecord:
        return upsert_schain_record(self.name)

    @BaseActionManager.monitor_block
    def config_dir(self) -> bool:
        logger.info('Initializing config dir')
        init_schain_config_dir(self.name)
        return True

    @BaseActionManager.monitor_block
    def dkg(self) -> bool:
        initial_status = self.checks.dkg.status
        with self.statsd_client.timer(f'admin.action.dkg.{no_hyphens(self.name)}'):
            if not initial_status:
                logger.info('Initializing dkg client')
                dkg_client = get_dkg_client(
                    skale=self.skale,
                    node_id=self.node_config.id,
                    schain_name=self.name,
                    sgx_key_name=self.node_config.sgx_key_name,
                    rotation_id=self.rotation_id,
                    chain_name=self.name,
                )
                logger.info('Running run_dkg')
                dkg_result = run_dkg(
                    dkg_client=dkg_client,
                    skale=self.skale,
                    schain_name=self.name,
                    rotation_id=self.rotation_id,
                )
                logger.info('DKG finished with %s', dkg_result)
                if dkg_result.status.is_done():
                    save_dkg_results(
                        dkg_result.keys_data,
                        get_secret_key_share_filepath(self.name, self.rotation_id),
                    )
                self.chain_record.set_dkg_status(dkg_result.status)
                if not dkg_result.status.is_done():
                    raise DkgError('DKG failed')
            else:
                logger.info('Dkg - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def upstream_config(self) -> bool:
        with self.statsd_client.timer(f'admin.action.upstream_config.{no_hyphens(self.name)}'):
            logger.info(
                'Generating new upstream_config rotation_id: %s, stream: %s',
                self.rotation_data.rotation_counter,
                self.stream_version,
            )
            new_config = create_new_upstream_config(
                skale=self.skale,
                skale_ima=self.skale_ima,
                node_config=self.node_config,
                schain_name=self.name,
                generation=self.generation,
                ecdsa_sgx_key_name=self.node_config.sgx_key_name,
                rotation_data=self.rotation_data,
                sync_node=SYNC_NODE,
                node_options=self.node_options,
            )

            result = False
            if (
                not self.cfm.upstream_config_exists()
                or new_config != self.cfm.latest_upstream_config
            ):
                logger.info('Saving new config')
                rotation_id = self.rotation_data.rotation_counter
                logger.info(
                    'Saving new upstream config rotation_id: %d, ips: %s',
                    rotation_id,
                    self.current_nodes,
                )
                self.cfm.save_new_upstream(rotation_id, new_config)
                result = True
            else:
                logger.info('Generated config is the same as latest upstream')

            update_schain_config_version(self.name, chain_record=self.chain_record)
            return result

    @BaseActionManager.monitor_block
    def reset_config_record(self) -> bool:
        update_schain_config_version(self.name, chain_record=self.chain_record)
        self.chain_record.set_sync_config_run(False)
        return True

    @BaseActionManager.monitor_block
    def external_state(self) -> bool:
        logger.info('Updating external state config')
        logger.debug('New state %s', self.estate)
        self.econfig.update(self.estate)
        return True

    @BaseActionManager.monitor_block
    def update_reload_ts(self, ip_matched: CheckRes, sync_node: bool = False) -> bool:
        """
        - If ip_matched is True, then config is synced and skaled reload is not needed
        - If ip_matched is False, then config is not synced and skaled reload is needed

        For sync node node_index_in_group is always 0 to reload sync nodes immediately
        """
        logger.info('Setting reload_ts')
        if ip_matched:
            logger.info('Resetting reload_ts')
            self.estate.reload_ts = None
            self.econfig.update(self.estate)
            return True

        node_index_in_group = 0
        if not sync_node:
            node_index_in_group = get_node_index_in_group(
                self.skale, self.name, self.node_config.id
            )
            if node_index_in_group is None:
                logger.warning(f'node {self.node_config.id} is not in chain {self.name}')
                return False
        self.estate.reload_ts = calc_reload_ts(self.current_nodes, node_index_in_group)
        logger.info(f'Setting reload_ts to {self.estate.reload_ts}')
        self.econfig.update(self.estate)
        return True
