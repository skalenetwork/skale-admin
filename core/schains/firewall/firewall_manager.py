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
from typing import Iterable, Optional

from core.schains.firewall.iptables import IptablesController
from core.schains.firewall.types import (
    IFirewallManager,
    IHostFirewallController,
    SChainRule
)


logger = logging.getLogger(__name__)


class SChainFirewallManager(IFirewallManager):
    def __init__(
        self,
        name: str,
        first_port: int,
        last_port: int
    ) -> None:
        self.name = name
        self.first_port = first_port
        self.last_port = last_port
        self._host_controller: Optional[IHostFirewallController] = None

    @abstractmethod
    def create_host_controller(
        self
    ) -> IHostFirewallController:  # pragma: no cover
        pass

    @property
    def host_controller(self) -> IHostFirewallController:
        if not self._host_controller:
            self._host_controller = self.create_host_controller()
        return self._host_controller

    @property
    def rules(self) -> Iterable[SChainRule]:
        return sorted(list(filter(
            lambda r: self.first_port <= r.port <= self.last_port,
            self.host_controller.rules
        )))

    def update_rules(self, rules: Iterable[SChainRule]) -> None:
        actual_rules = set(self.rules)
        expected_rules = set(rules)
        rules_to_add = expected_rules - actual_rules
        rules_to_remove = actual_rules - expected_rules
        self.add_rules(rules_to_add)
        self.remove_rules(rules_to_remove)

    def add_rules(self, rules: Iterable[SChainRule]) -> None:
        logger.debug('Adding rules %s', rules)
        for rule in sorted(rules):
            self.host_controller.add_rule(rule)

    def remove_rules(self, rules: Iterable[SChainRule]) -> None:
        logger.debug('Removing rules %s', rules)
        for rule in rules:
            self.host_controller.remove_rule(rule)

    def flush(self) -> None:
        self.remove_rules(self.rules)


class IptablesSChainFirewallManager(SChainFirewallManager):
    def create_host_controller(self) -> IptablesController:
        return IptablesController()
