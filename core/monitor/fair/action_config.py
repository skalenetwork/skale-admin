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

from skale import FairManager
from skale.types.dkg import DkgId

from core.checks.fair import FairConfigChecks
from core.config.fair.generator import generate_fair_config_with_manager
from core.config.schain.directory import init_schain_config_dir
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.main import update_schain_config_version
from core.dkg.fair.main import get_dkg_client, run_dkg
from core.dkg.utils import DkgError, get_secret_key_share_filepath, save_dkg_results
from core.firewall import get_fair_network_scope_rule_controller, get_network_scope_node_ips
from core.monitor.action_base import BaseActionManager
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.redis.node_config_fair import NodeConfigFair
from core.types.chain import FairChainName
from core.utils.fair import get_local_skaled_endpoint_fair
from tools.helper import no_hyphens
from tools.node_options import NodeOptions
from tools.resources import get_statsd_client

logger = logging.getLogger(__name__)


class FairConfigActionManager(BaseActionManager):
    def __init__(
        self,
        fair: FairManager,
        chain_name: FairChainName,
        dkg_id: DkgId,
        node_config: NodeConfig,
        stream_version: str,
        checks: FairConfigChecks,
        node_options: NodeOptions | None = None,
    ):
        self.fair = fair
        self.node_config = node_config
        self.checks = checks
        self.stream_version = stream_version
        self.chain_name = chain_name
        self.dkg_id = dkg_id
        self.rule_controller = get_fair_network_scope_rule_controller()

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
                logger.info('Initializing fair dkg client')
                dkg_client = get_dkg_client(
                    self.node_config.id,
                    self.fair,
                    self.node_config.sgx_key_name,
                    dkg_id=self.dkg_id,
                    chain_name=self.name,
                )
                logger.info('Running run_dkg')
                dkg_result = run_dkg(self.fair, dkg_client)
                logger.info('DKG finished with %s', dkg_result)
                if dkg_result.status.is_done():
                    save_dkg_results(
                        dkg_result.keys_data,
                        get_secret_key_share_filepath(self.name, self.dkg_id),
                    )
                self.chain_record.set_dkg_status(dkg_result.status)
                if not dkg_result.status.is_done():
                    raise DkgError('DKG failed')
            else:
                logger.info('Dkg - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def upstream_config(self, is_committee_node: bool) -> bool:
        with self.statsd_client.timer(f'admin.action.upstream_config.{no_hyphens(self.name)}'):
            logger.info(
                'Generating new upstream_config dkg_id: \
%s, stream: %s, is_committee_node: %s',
                self.dkg_id,
                self.stream_version,
                is_committee_node,
            )

            new_config = generate_fair_config_with_manager(
                fair=self.fair,
                node_id=self.node_config.id,
                ecdsa_key_name=self.node_config.sgx_key_name,
                is_committee_node=is_committee_node,
                archive=self.node_options.archive,
                catchup=self.node_options.catchup,
            ).to_dict()

            result = False
            if (
                not self.cfm.upstream_config_exists()
                or new_config != self.cfm.latest_upstream_config
            ):
                logger.info('Saving new config')
                logger.info('Saving new upstream config dkg_id: %d', self.dkg_id)
                self.cfm.save_new_upstream(self.dkg_id, new_config)
                result = True
            else:
                logger.info('Generated config is the same as latest upstream')

            self.update_local_skaled_endpoint()
            update_schain_config_version(self.name, chain_record=self.chain_record)
            return result

    def update_local_skaled_endpoint(self) -> None:
        local_endpoint = get_local_skaled_endpoint_fair()
        if local_endpoint:
            node_config_fair = NodeConfigFair()
            node_config_fair.set_local_endpoint(local_endpoint)
        else:
            logger.info('Local skaled endpoint is not set, skipping node_config_fair update')

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
            base_port = self.fair.nodes.get(self.node_config.id).port
            own_ip = self.node_config.ip
            node_ips = get_network_scope_node_ips(self.fair)

            self.rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
            self.rule_controller.sync()
        return initial_status
