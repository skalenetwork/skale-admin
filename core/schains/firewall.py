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


from collections import namedtuple
from typing import Dict, List, Optional, Set

from core.schains.config.helper import get_allowed_endpoints
from tools.iptables import (
    IptablesManager,
    add_rules as add_iptables_rules,
    remove_rules as remove_iptables_rules
)

SChainRule = namedtuple(
    'SChainRule',
    ['name', 'port', 'start_ip', 'end_ip']
)


class SChainFirewall:
    def __init__(
        self,
        name: str,
        base_port: int,
        own_ip: str,
        node_ips: List[str],
        sync_agent_ips: List[str],
        iptables_manager: Optional[IptablesManager] = None
    ) -> None:
        self.name = name,
        self.iptables_manager = iptables_manager or IptablesManager()
        self.base_port = base_port
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.sync_agent_ips = sync_agent_ips

    def get_rules(self) -> Set[SChainRule]:
        return set(map(
            lambda rd: self.rule_d_to_schain_rule(rd),
            self.iptables_manager.get_rules()
        ))

    def schain_rule_to_rule_d(self, srule: SChainRule) -> List:
        return self.iptables_manager.compose_rule_d(
            port=srule.port,
            start_ip=srule.start_ip,
            end_ip=srule.end_ip,
        )

    def rule_d_to_schain_rule(self, rule_d: Dict) -> SChainRule:
        start_ip, end_ip = None, None
        iprange = rule_d.get('iprange')
        if iprange:
            start_ip, end_ip = iprange['src-range'].split('-')
        else:
            start_ip = end_ip = rule_d['src']

        return SChainRule(
            name=self.name,
            port=rule_d['tcp']['dport'],
            start_ip=start_ip,
            end_ip=end_ip
        )

    def add_rules(self, rules: List[SChainRule]) -> None:
        for rule in rules:
            self.iptables_manager.ensure_rule_added(rule)

    def remove_rules(self, rules: List[SChainRule]) -> None:
        for rule in rules:
            self.iptables_manager.ensure_rule_added(rule)


def add_firewall_rules(schain_name, endpoints=None):
    endpoints = endpoints or get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def remove_firewall_rules(schain_name, endpoints=None):
    endpoints = endpoints or get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)
