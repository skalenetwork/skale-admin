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

from typing import Iterable
from core.schains.firewall.types import IHostFirewallManager, SChainRule


logger = logging.getLogger(__name__)


class SChainFirewallManager:
    def __init__(
        self,
        name: str,
        first_port: int,
        last_port: int,
        host_manager: IHostFirewallManager
    ) -> None:
        self.name = name
        self.first_port = first_port
        self.last_port = last_port
        self.host_manager = host_manager

    @property
    def rules(self) -> Iterable[SChainRule]:
        return sorted(list(filter(
            lambda r: self.first_port <= r.port <= self.last_port,
            self.host_manager.rules
        )))

    def update_rules(self, rules: Iterable[SChainRule]) -> None:
        actual_rules = set(self.rules)
        expected_rules = set(rules)
        rules_to_add = expected_rules - actual_rules
        rules_to_remove = actual_rules - expected_rules
        self.add_rules(rules_to_add)
        self.remove_rules(rules_to_remove)

    def add_rules(self, rules: Iterable[SChainRule]) -> None:
        for rule in rules:
            self.host_manager.add_rule(rule)

    def remove_rules(self, rules: Iterable[SChainRule]) -> None:
        for rule in rules:
            self.host_manager.remove_rule(rule)
