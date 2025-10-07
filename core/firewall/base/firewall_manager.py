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

from .nftables import NFTablesController
from .types import IFirewallManager, SChainRule

logger = logging.getLogger(__name__)


class ChainFirewallManager(IFirewallManager):
    def __init__(self, group: str, first_port: int, last_port: int) -> None:
        self.group = group
        self.first_port = first_port
        self.last_port = last_port
        self._host_controller: Optional[NFTablesController] = None

    @abstractmethod
    def create_host_controller(self) -> NFTablesController:  # pragma: no cover
        pass

    @property
    def host_controller(self) -> NFTablesController:
        if not self._host_controller:
            self._host_controller = self.create_host_controller()
        return self._host_controller

    @property
    def rules(self) -> Iterable[SChainRule]:
        return sorted(
            list(
                filter(
                    lambda r: self.first_port <= r.first_port <= r.last_port <= self.last_port,
                    self.host_controller.rules,
                )
            )
        )

    def update_rules(self, rules: Iterable[SChainRule]) -> None:
        actual_rules = set(self.rules)
        expected_rules = set(rules)
        rules_to_add = expected_rules - actual_rules
        rules_to_remove = actual_rules - expected_rules
        self.add_rules(rules_to_add)
        self.remove_rules(rules_to_remove)
        self.save_rules()

    def save_rules(self) -> None:
        """Saves rules into persistent storage"""
        self.host_controller.save_rules()

    def add_rules(self, rules: Iterable[SChainRule]) -> None:
        logger.debug('Adding rules %s', rules)
        for rule in sorted(rules):
            self.host_controller.add_rule(rule)

    def remove_rules(self, rules: Iterable[SChainRule]) -> None:
        logger.debug('Removing rules %s', rules)
        for rule in rules:
            self.host_controller.remove_rule(rule)


class NFTChainFirewallManager(ChainFirewallManager):
    def create_host_controller(self) -> NFTablesController:
        nc_controller = NFTablesController(chain=self.group)
        nc_controller.create_table()
        nc_controller.create_chain(self.first_port, self.last_port)
        return nc_controller

    def rules_saved(self) -> bool:
        saved = self.host_controller.get_saved_rules()
        if saved == '':
            return False
        return saved == self.host_controller.get_plain_chain_rules()

    def base_config_applied(self) -> bool:
        return self.host_controller.has_chain(self.host_controller.chain)

    def cleanup(self) -> None:
        self.host_controller.cleanup()
        self.host_controller.remove_saved_rules()
