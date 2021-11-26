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
from typing import List, Optional

from skale import Skale

from .firewall_manager import SChainFirewallManager
from .types import IpRange, PORTS_PER_SCHAIN
from .iptables import IptablesManager
from .rule_controller import SChainRuleController


logger = logging.getLogger(__name__)


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
    logger.info('Creating rc port: %s, own ip: %s', base_port, own_ip)
    logger.debug('Rule controller ips %s, %s', node_ips, sync_agent_ranges)
    return SChainRuleController(
        fm,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )


def get_sync_agent_ranges(skale: Skale) -> List[IpRange]:
    sync_agent_ranges = []
    rnum = skale.sync_manager.get_ip_ranges_number()
    for i in range(rnum):
        sync_agent_ranges.append(skale.sync_manager.get_ip_range_by_index(i))
    return sync_agent_ranges
