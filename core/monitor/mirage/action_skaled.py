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

from core.chain.runner import is_container_exists
from core.monitor.action_base import (
    BaseActionManager,
    BaseSkaledActionManager,
)
from core.node_config import NodeConfig
from core.checks.mirage import SkaledChecks

from core.firewall.types import IRuleController
from core.chain.volume import init_mirage_volume
from core.schains.cleaner import remove_skaled_container

from core.config.schain.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
)

from core.types.chain import MirageChainName
from tools.configs.containers import SKALED_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import no_hyphens
from tools.node_options import NodeOptions


logger = logging.getLogger(__name__)


class MirageSkaledActionManager(BaseSkaledActionManager):
    def __init__(
        self,
        chain_name: MirageChainName,
        rule_controller: IRuleController,
        checks: SkaledChecks,
        node_config: NodeConfig,
        dutils: DockerUtils | None = None,
        node_options: NodeOptions | None = None,
    ):
        super().__init__(
            chain_name=chain_name,
            rule_controller=rule_controller,
            checks=checks,
            node_config=node_config,
            dutils=dutils,
            node_options=node_options,
        )
        self.chain_name = chain_name

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            logger.info('Creating volume')
            init_mirage_volume(self.chain_name, dutils=self.dutils)
        else:
            logger.info('Volume - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def firewall_rules(self, upstream: bool = False) -> bool:
        initial_status = self.checks.firewall_rules.status
        # todod: use new approach for firewall rules (only internal ports)
        if not initial_status:
            logger.info('Configuring firewall rules')

            conf = self.cfm.latest_upstream_config if upstream else self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)

            logger.debug('Base port %d', base_port)
            with self.statsd_client.timer(f'admin.action.firewall.{no_hyphens(self.name)}'):
                self.rc.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
                self.statsd_client.gauge(
                    f'admin.action.expected_rules.{no_hyphens(self.name)}',
                    len(self.rc.expected_rules()),
                )
                self.rc.sync()
        return initial_status

    @BaseActionManager.monitor_block
    def recreated_schain_containers(self, abort_on_exit: bool = True) -> bool:
        logger.info('Restart skaled from scratch')
        initial_status = True
        if is_container_exists(self.name, container_type=SKALED_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_skaled_container(self.name, dutils=self.dutils)
        self.chain_record.set_restart_count(0)
        self.chain_record.set_failed_rpc_count(0)
        self.skaled_container(abort_on_exit=abort_on_exit)
        return initial_status
