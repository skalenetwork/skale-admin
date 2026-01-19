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

import json
import logging
import socket
from typing import List, Optional

from skale import FairManager, SkaleManager

from tools.configs.fair import NFT_COMMITTEE_SCOPE_CHAIN, NFT_NETWORK_SCOPE_CHAIN

from .base.nftables import NFTablesController
from .base.types import IpRange
from .fair.rule_controller import (
    FairCommitteeScopeRuleController,
    FairNetworkScopeRuleController,
)
from .schain.rule_controller import NFTSchainRuleController

logger = logging.getLogger(__name__)


def get_default_rule_controller(
    name: str,
    base_port: Optional[int] = None,
    own_ip: Optional[str] = None,
    node_ips: List[str] = [],
    sync_agent_ranges: Optional[List[IpRange]] = [],
) -> NFTSchainRuleController:
    return get_nftables_rule_controller(
        name=name,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips,
        sync_agent_ranges=sync_agent_ranges,
    )


def get_fair_network_scope_rule_controller(
    base_port: Optional[int] = None,
    own_ip: Optional[str] = None,
    node_ips: List[str] = [],
):
    return FairNetworkScopeRuleController(
        controller_name=NFT_NETWORK_SCOPE_CHAIN,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips,
    )


def get_fair_committee_scope_rule_controller(
    base_port: Optional[int] = None,
    own_ip: Optional[str] = None,
    node_ips: List[str] = [],
):
    return FairCommitteeScopeRuleController(
        controller_name=NFT_COMMITTEE_SCOPE_CHAIN,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips,
    )


def get_nftables_rule_controller(
    name: str,
    base_port: Optional[int] = None,
    own_ip: Optional[str] = None,
    node_ips: List[str] = [],
    sync_agent_ranges: Optional[List[IpRange]] = [],
) -> NFTSchainRuleController:
    sync_agent_ranges = sync_agent_ranges or []
    logger.info('Creating rule controller for %s', name)
    logger.debug('Rule controller ranges for %s: %s', name, sync_agent_ranges)
    return NFTSchainRuleController(
        name=name,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips,
        sync_ip_ranges=sync_agent_ranges,
    )


def get_sync_agent_ranges(skale: SkaleManager) -> List[IpRange]:
    sync_agent_ranges = []
    rnum = skale.sync_manager.get_ip_ranges_number()
    for i in range(rnum):
        sync_agent_ranges.append(skale.sync_manager.get_ip_range_by_index(i))
    return sorted(sync_agent_ranges)


def save_sync_ranges(sync_agent_ranges: List[IpRange], path: str) -> None:
    output = {'ranges': [list(r) for r in sync_agent_ranges]}
    with open(path, 'w') as out_file:
        json.dump(output, out_file)


def cleanup_firewall_for_schain(schain_name: str) -> None:
    nft = NFTablesController(chain=schain_name)
    nft.cleanup()
    nft.remove_saved_rules()


def get_network_scope_node_ips(fair: FairManager) -> List[str]:
    passive_node_ids = fair.nodes.get_passive_node_ids()
    active_node_ids = fair.nodes.active_node_ids()
    node_ids = [*passive_node_ids, *active_node_ids]
    node_ips_raw = [fair.nodes.get(node_id).ip for node_id in node_ids]
    return [socket.inet_ntoa(raw_ip) for raw_ip in node_ips_raw]
