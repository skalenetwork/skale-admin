#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
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
import os
from typing import cast

from skale.fair_manager import FairManager
from skale.types.committee import CommitteeIndex

from core.checks.base import BaseSkaledChecks, CheckRes, IChecks
from core.config.endpoint import get_base_port_from_config
from core.config.fair.firewall import (
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.config.schain.file_manager import ConfigFileManager
from core.firewall import get_fair_network_scope_rule_controller, get_network_scope_node_ips
from core.firewall.fair import (
    FairCommitteeScopeRuleController,
    FairNetworkScopeRuleController,
)
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.dkg.utils import get_secret_key_share_filepath
from core.types.chain import FairChainName
from tools.resources import get_statsd_client
from tools.helper import cast_manager_to_fair_node_id

logger = logging.getLogger(__name__)


def get_base_port_from_fair_manager(fair: FairManager, node_config: NodeConfig) -> int:
    # todod: Should be changed after corresponding changes are made in fair manager.
    node_id = cast_manager_to_fair_node_id(node_config.id)
    return fair.nodes.get(node_id).port


class FairConfigChecks(IChecks):
    def __init__(
        self,
        fair: FairManager,
        node_config: NodeConfig,
        chain_name: FairChainName,
        committee_index: CommitteeIndex,
        stream_version: str,
        chain_record: ChainRecord,
    ) -> None:
        self.name = chain_name
        self.node_config = node_config
        self.fair = fair
        self.chain_record = chain_record
        self.committee_index = committee_index
        self.stream_version = stream_version
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=chain_name)
        self.statsd_client = get_statsd_client()

        self.rule_controller: FairNetworkScopeRuleController = (
            get_fair_network_scope_rule_controller()
        )

    def get_name(self) -> str:
        return self.name

    @property
    def config_dir(self) -> CheckRes:
        """Checks that sChain config directory exists"""
        dir_path = self.cfm.dirname
        return CheckRes(os.path.isdir(dir_path))

    @property
    def dkg(self) -> CheckRes:
        """Checks that DKG procedure is completed"""
        secret_key_share_filepath = get_secret_key_share_filepath(self.name, self.committee_index)
        return CheckRes(os.path.isfile(secret_key_share_filepath))

    @property
    def upstream_config(self) -> CheckRes:
        """
        Returns True if config exists for current rotation id,
        node ip addresses and stream version are up to date
        and config regeneration was not triggered manually.
        Returns False otherwise.
        """
        exists = self.cfm.upstream_exist_for_rotation_id(self.committee_index)
        logger.debug('Upstream configs status for %s: %s', self.name, exists)
        stream_updated = self.chain_record.config_version == self.stream_version
        triggered = self.chain_record.sync_config_run

        logger.info(
            'Upstream config status, committee_index %s: exist: %s,stream: %s, triggered: %s',
            self.committee_index,
            exists,
            stream_updated,
            triggered,
        )
        return CheckRes(exists and stream_updated and not triggered)

    @property
    def network_scope_firewall_rules(self) -> CheckRes:
        """Checks that network scope firewall rules are set correctly"""
        data = {
            'inited': False,
            'rules': False,
            'persistent': False,
        }
        base_port = get_base_port_from_fair_manager(self.fair, self.node_config)
        own_ip = self.node_config.ip
        node_ips = get_network_scope_node_ips(self.fair)

        self.rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
        if not self.rule_controller.is_inited():
            logger.debug('Network scope firewall rules are not initialized')
            return CheckRes(status=False, data=data)
        else:
            logger.debug(
                'Network scope check expected rules %s', self.rule_controller.expected_rules()
            )
            data.update(
                {
                    'inited': self.rule_controller.is_inited(),
                    'rules': self.rule_controller.is_rules_synced(),
                    'persistent': self.rule_controller.is_persistent(),
                }
            )
            logger.debug('Network scope firewall rules check: %s', data)
            status = all(data.values())
            return CheckRes(status=status, data=data)


class SkaledChecks(BaseSkaledChecks):
    @property
    def committee_scope_firewall_rules(self) -> CheckRes:
        """Checks that committee scope firewall rules are set correctly"""
        data = {
            'inited': False,
            'rules': False,
            'persistent': False,
        }
        if self.config:
            conf = self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)
            fair_rule_controller = cast(FairCommitteeScopeRuleController, self.rule_controller)
            fair_rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
            logger.debug(
                'Committee scope check expected rules %s', self.rule_controller.expected_rules()
            )
            data.update(
                {
                    'inited': self.rule_controller.is_inited(),
                    'rules': self.rule_controller.is_rules_synced(),
                    'persistent': self.rule_controller.is_persistent(),
                }
            )
            logger.debug('Committee scope firewall rules check: %s', data)
            status = all(data.values())
            return CheckRes(status=status, data=data)
        return CheckRes(status=False, data=data)
