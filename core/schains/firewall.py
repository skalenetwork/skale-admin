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


from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Generator, List, Iterable


SChainRule = namedtuple(
    'SChainRule',
    ['port', 'first_ip', 'last_ip']
)


class IFirewallManager(ABC):
    @abstractmethod
    def add_rule(self, rule: SChainRule) -> None:
        pass

    @abstractmethod
    def remove_rule(self, rule: SChainRule) -> int:
        pass

    @property
    @abstractmethod
    def rules(self) -> Generator[SChainRule, SChainRule, SChainRule]:
        pass

    @abstractmethod
    def has_rule(self, rule: SChainRule) -> bool:
        pass


class SChainFirewall:
    def __init__(
        self,
        name: str,
        first_port: int,
        last_port: int,
        own_ip: str,
        node_ips: List[str],
        sync_agent_ips: List[str],
        firewall_manager: IFirewallManager
    ) -> None:
        self.name = name,
        self.firewall_manager = firewall_manager
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.sync_agent_ips = sync_agent_ips

    def get_rules(
        self,
        first_port,
        last_port
    ) -> Generator[SChainRule, SChainRule, SChainRule]:
        return filter(
            lambda r: self.first_port <= r.port <= self.last_port,
            self.firewall_manager.rules
        )

#     def schain_rule_to_rule_d(self, srule: SChainRule) -> List:
#         return self.firewall_manager.compose_rule_d(
#             port=srule.port,
#             start_ip=srule.start_ip,
#             end_ip=srule.end_ip,
#         )
#
#     def rule_d_to_schain_rule(self, rule_d: Dict) -> SChainRule:
#         start_ip, end_ip = None, None
#         iprange = rule_d.get('iprange')
#         if iprange:
#             start_ip, end_ip = iprange['src-range'].split('-')
#         else:
#             start_ip = end_ip = rule_d['src']
#
#         return SChainRule(
#             name=self.name,
#             port=rule_d['tcp']['dport'],
#             start_ip=start_ip,
#             end_ip=end_ip
#         )

    def update_rules(self, rules: Iterable[SChainRule]) -> None:
        actual_rules = set(self.firewall_manager.rules)
        expected_rules = set(rules)
        rules_to_add = expected_rules - actual_rules
        rules_to_remove = actual_rules - expected_rules
        self.add_rules(rules_to_add)
        self.remove_rules(rules_to_remove)

    def add_rules(self, rules: Iterable[SChainRule]) -> None:
        for rule in rules:
            self.firewall_manager.add_rule(rule)

    def remove_rules(self, rules: Iterable[SChainRule]) -> None:
        for rule in rules:
            self.firewall_manager.remove_rule(rule)
