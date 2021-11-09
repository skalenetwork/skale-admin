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

from typing import List, Optional

from .firewall_manager import SChainFirewallManager
from .entities import IpRange, PORTS_PER_SCHAIN
from .iptables import IptablesManager
from .rule_controller import SChainRuleController


def get_default_rule_controller(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: Optional[List[IpRange]] = None
) -> SChainRuleController:
    sync_agent_ranges = sync_agent_ranges or []
    im = IptablesManager()
    fm = SChainFirewallManager(
        name,
        base_port,
        base_port + PORTS_PER_SCHAIN,
        im
    )
    return SChainRuleController(
        fm,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )


def is_rules_synced(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: List[IpRange]
):
    rc = get_default_rule_controller(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_agent_ranges
    )
    return rc.is_rules_synced()


def sync_rules(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: List[IpRange]
):
    rc = get_default_rule_controller(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_agent_ranges
    )
    return rc.sync_rules()
