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

import itertools
import logging
from abc import abstractmethod
from functools import wraps
from typing import Any, Callable, cast, Dict, Iterable, List, Optional, TypeVar

from .firewall_manager import NFTMirageChainFirewallManager
from ..base.types import (
    Action,
    IRuleController,
    PORTS_PER_SCHAIN,
    SChainRule,
    LOOPBACK_INTERFACE,
    SkaledPorts,
)


logger = logging.getLogger(__name__)


class NotInitializedError(Exception):
    pass


F = TypeVar('F', bound=Callable[..., Any])


def configured_only(func: F) -> F:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.is_configured():
            return func(self, *args, **kwargs)
        else:
            missing = self.get_missing()
            raise NotInitializedError(f'Missing fields {missing}')

    return cast(F, wrapper)


class MirageController(IRuleController):
    def __init__(
        self,
        controller_name: str,
        base_port: Optional[int] = None,
        own_ip: Optional[str] = None,
        node_ips: List[str] = [],
        port_allocation: Any = SkaledPorts,  # TODO: better typing for enum
        ports_per_schain: int = PORTS_PER_SCHAIN,
    ) -> None:
        self.name = controller_name
        self.base_port = base_port
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.port_allocation = port_allocation
        self.ports_per_schain = ports_per_schain
        self._firewall_manager = None

    def is_configured(self) -> bool:
        return all((self.base_port, self.node_ips))

    def get_missing(self) -> Dict['str', Any]:
        missing: Dict['str', Any] = {}
        if not self.base_port:
            missing.update({'base_port': self.base_port})
        if not self.own_ip:
            missing.update({'own_ip': self.own_ip})
        if not self.node_ips:
            missing.update({'node_ips': self.node_ips})
        return missing

    @property
    def firewall_manager(self) -> NFTMirageChainFirewallManager:
        if not self._firewall_manager:
            self._firewall_manager = self.create_firewall_manager()
        return self._firewall_manager

    @configured_only
    def create_firewall_manager(self) -> NFTMirageChainFirewallManager:
        return NFTMirageChainFirewallManager(
            self.name,
            self.base_port,  # type: ignore
            self.base_port + self.ports_per_schain - 1,  # type: ignore
        )

    def configure(
        self,
        base_port: Optional[int] = None,
        own_ip: Optional[str] = None,
        node_ips: Optional[List[str]] = None,
        port_allocation: Any = SkaledPorts,
    ) -> None:
        self.base_port = base_port or self.base_port
        self.own_ip = own_ip or self.own_ip
        self.node_ips = node_ips or self.node_ips
        self.port_allocation = port_allocation or self.port_allocation

    @configured_only
    def is_rules_synced(self) -> bool:
        actual = set(self.actual_rules())
        expected = set(self.expected_rules())
        logger.debug('Rules status: actual %s, expected %s', actual, expected)
        logger.info(
            'Rules status: missing rules %d, redundant rules: %d',
            len(expected - actual),
            len(actual - expected),
        )
        return actual == expected

    @configured_only
    def actual_rules(self) -> Iterable[SChainRule]:
        return sorted(self.firewall_manager.rules)

    @configured_only
    @abstractmethod
    def expected_rules(self) -> Iterable[SChainRule]:
        pass

    def sync(self) -> None:
        erules = self.expected_rules()
        logger.info('Syncing firewall rules')
        logger.debug('Syncing firewall rules with %s', erules)
        self.firewall_manager.update_rules(erules)

    @configured_only
    def is_persistent(self) -> bool:
        return self.firewall_manager.rules_saved()

    @configured_only
    def is_inited(self) -> bool:
        return self.firewall_manager.base_config_applied()

    def cleanup(self) -> None:
        self.firewall_manager.cleanup()


class MirageNetworkScopeRuleController(MirageController):
    @property
    def public_ports(self) -> Iterable[int]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.HTTP_JSON,
                self.port_allocation.HTTPS_JSON,
                self.port_allocation.WS_JSON,
                self.port_allocation.WSS_JSON,
            )
        )

    @property
    def public_rules(self) -> Iterable[SChainRule]:
        return (SChainRule(first_port=port) for port in self.public_ports)

    @property
    def network_scope_ports(self) -> Iterable[int]:
        return (
            self.base_port + offset.value
            for offset in (self.port_allocation.CATCHUP, self.port_allocation.ZMQ_BROADCAST)
        )

    @property
    def drop_rules(self) -> Iterable[SChainRule]:
        return [
            SChainRule(
                first_port=port,
                action=Action.DROP,
                interface_exception=LOOPBACK_INTERFACE,
            )
            for port in self.network_scope_ports
        ]

    @property
    @configured_only
    def network_scope_rules(self) -> Iterable[SChainRule]:
        for ip in self.node_ips:
            if ip != self.own_ip:
                for port in self.network_scope_ports:
                    yield SChainRule(first_port=port, first_ip=ip)

    @configured_only
    def expected_rules(self) -> Iterable[SChainRule]:

        return sorted(
            itertools.chain.from_iterable(
                (self.public_rules, self.network_scope_rules , self.drop_rules))
        )


class MirageCommitteeScopeRuleController(MirageController):
    @property
    def committee_scope_ports(self) -> Iterable[int]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.PROPOSAL,
                self.port_allocation.BINARY_CONSENSUS,
            )
        )

    @property
    def drop_rules(self) -> Iterable[SChainRule]:
        return [
            SChainRule(
                first_port=port,
                action=Action.DROP,
                interface_exception=LOOPBACK_INTERFACE,
            )
            for port in self.committee_scope_ports
        ]

    @property
    @configured_only
    def committee_scope_rules(self) -> Iterable[SChainRule]:
        for ip in self.node_ips:
            if ip != self.own_ip:
                for port in self.committee_scope_ports:
                    yield SChainRule(first_port=port, first_ip=ip)

    @configured_only
    def expected_rules(self) -> Iterable[SChainRule]:
        return sorted(
            itertools.chain.from_iterable(
                (self.committee_scope_rules, [], self.drop_rules)))
