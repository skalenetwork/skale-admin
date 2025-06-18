#   -*- coding: utf-8 -*-
#
#  This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

from skale import MirageManager

from core.config.mirage.generator import generate_mirage_config_with_manager
from core.monitor.action_base import BaseActionManager
from core.node_config import NodeConfig
from core.checks.mirage import MirageConfigChecks
from core.firewall import get_mirage_network_scope_rule_controller, get_network_scope_node_ips
from core.redis.chain_record import ChainRecord


from core.config.schain.directory import init_schain_config_dir
from core.config.schain.main import update_schain_config_version
from core.config.schain.file_manager import ConfigFileManager

from core.types.chain import MirageChainName
from tools.configs import SYNC_NODE
from tools.helper import no_hyphens
from tools.node_options import NodeOptions
from tools.resources import get_statsd_client


logger = logging.getLogger(__name__)


class MirageConfigActionManager(BaseActionManager):
    def __init__(
        self,
        mirage: MirageManager,
        chain_name: MirageChainName,
        group_index: int,
        node_config: NodeConfig,
        stream_version: str,
        checks: MirageConfigChecks,
        node_options: NodeOptions | None = None,
    ):
        self.mirage = mirage
        self.node_config = node_config
        self.checks = checks
        self.stream_version = stream_version
        self.chain_name = chain_name
        self.group_index = group_index
        self.rule_controller = get_mirage_network_scope_rule_controller()

        self.node_options = node_options or NodeOptions()
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=self.chain_name)
        self.statsd_client = get_statsd_client()
        super().__init__(name=self.chain_name)

    @property
    def chain_record(self) -> ChainRecord:
        return ChainRecord(name=self.chain_name)

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
                # todod: get_mirage_dkg_client

                # dkg_client = get_dkg_client(
                #     skale=self.skale,
                #     node_id=self.node_config.id,
                #     schain_name=self.name,
                #     sgx_key_name=self.node_config.sgx_key_name,
                #     rotation_id=self.rotation_id,
                # )
                logger.info('Running run_dkg')
                # todod: run_mirage_dkg

                # dkg_result = run_dkg(
                #     dkg_client=dkg_client,
                #     skale=self.skale,
                #     schain_name=self.name,
                #     node_id=self.node_config.id,
                #     sgx_key_name=self.node_config.sgx_key_name,
                #     rotation_id=self.rotation_id,
                # )
                # logger.info('DKG finished with %s', dkg_result)
                # if dkg_result.status.is_done():
                #     save_dkg_results(
                #         dkg_result.keys_data,
                #         get_secret_key_share_filepath(self.name, self.rotation_id),
                #     )
                # self.chain_record.set_dkg_status(dkg_result.status)
                # if not dkg_result.status.is_done():
                #     raise DkgError('DKG failed')
            else:
                logger.info('Dkg - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def upstream_config(self) -> bool:
        with self.statsd_client.timer(f'admin.action.upstream_config.{no_hyphens(self.name)}'):
            logger.info(
                'Generating new upstream_config group_index: %s, stream: %s',
                self.group_index,
                self.stream_version,
            )

            new_config = generate_mirage_config_with_manager(
                mirage=self.mirage,
                node_id=self.node_config.id,
                group_index=self.group_index,
                ecdsa_key_name=self.node_config.sgx_key_name,
                sync_node=SYNC_NODE,
                archive=self.node_options.archive,
                catchup=self.node_options.catchup,
            ).to_dict()

            result = False
            if (
                not self.cfm.upstream_config_exists()
                or new_config != self.cfm.latest_upstream_config
            ):
                logger.info('Saving new config')
                logger.info('Saving new upstream config group_index: %d', self.group_index)
                self.cfm.save_new_upstream(self.group_index, new_config)
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
    def network_scope_firewall_rules(self) -> bool:
        initial_status = self.checks.network_scope_firewall_rules.status
        if not initial_status:
            logger.info('Configuring network scope firewall rules')
            base_port = self.node_config.schain_base_port
            own_ip = self.node_config.ip
            node_ips = get_network_scope_node_ips(self.mirage)

            self.rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
            self.rule_controller.sync()
        return initial_status
