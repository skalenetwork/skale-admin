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
from enum import Enum
from typing import Iterable, List, Optional

from core.schains.firewall.types import (
    IFirewallManager,
    IpRange,
    SChainRule,
    SkaledPorts
)

logger = logging.getLogger(__name__)


class SChainRuleController:
    def __init__(
        self,
        firewall_manager: IFirewallManager,
        base_port: int,
        own_ip: str,
        node_ips: List[str],
        port_allocation: Enum = SkaledPorts,
        sync_ip_ranges: Optional[List[IpRange]] = None
    ) -> None:
        self.base_port = base_port
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.sync_ip_ranges = sync_ip_ranges or []
        self.port_allocation = port_allocation
        self.firewall_manager = firewall_manager

    @property
    def internal_ports(self) -> Iterable[int]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.CATCHUP,
                self.port_allocation.PROPOSAL,
                self.port_allocation.BINARY_CONSENSUS,
                self.port_allocation.ZMQ_BROADCAST
            )
        )

    def configure(
        self,
        own_ip: str,
        node_ips: List[str],
        sync_ip_ranges: Optional[List[IpRange]] = None
    ) -> None:
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.sync_ip_ranges = sync_ip_ranges

    @property
    def internal_rules(self) -> Iterable[SChainRule]:
        for ip in self.node_ips:
            if ip != self.own_ip:
                for port in self.internal_ports:
                    yield SChainRule(port, ip)

    @property
    def public_ports(self) -> Iterable[int]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.HTTP_JSON,
                self.port_allocation.HTTPS_JSON,
                self.port_allocation.WS_JSON,
                self.port_allocation.WSS_JSON,
                self.port_allocation.INFO_HTTP_JSON,
                self.port_allocation.PG_HTTP_RPC_JSON,
                self.port_allocation.PG_HTTPS_RPC_JSON,
                self.port_allocation.PG_INFO_HTTP_RPC_JSON,
                self.port_allocation.PG_INFO_HTTPS_RPC_JSON,
            )
        )

    @property
    def public_rules(self) -> Iterable[SChainRule]:
        return (SChainRule(port) for port in self.public_ports)

    @property
    def sync_agent_port(self) -> int:
        return self.base_port + self.port_allocation.CATCHUP.value

    @property
    def sync_agent_rules(self) -> Iterable[SChainRule]:
        if not self.sync_ip_ranges:
            return []
        return (
            SChainRule(self.sync_agent_port, r.start_ip, r.end_ip)
            for r in self.sync_ip_ranges
        )

    def expected_rules(self) -> Iterable[SChainRule]:
        return sorted(itertools.chain.from_iterable((
            self.internal_rules,
            self.public_rules,
            self.sync_agent_rules
        )))

    def actual_rules(self) -> Iterable[SChainRule]:
        return sorted(self.firewall_manager.rules)

    def is_rules_synced(self) -> bool:
        actual = set(self.actual_rules())
        expected = set(self.expected_rules())
        logger.debug('Rules status: actual %s, expected %s', actual, expected)
        logger.info(
            'Rules status: missing rules %s, redundant rules: %s',
            expected - actual,
            actual - expected
        )
        return actual == expected

    def sync(self) -> None:
        erules = self.expected_rules()
        logger.info('Syncing firewall rules')
        logger.debug('Syncing firewall rules with %s', erules)
        self.firewall_manager.update_rules(erules)

    def cleanup(self) -> None:
        self.firewall_manager.flush()
