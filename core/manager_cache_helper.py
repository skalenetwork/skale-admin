#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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
from typing import Any

from eth_typing import ChecksumAddress
from skale import SkaleManager
from skale.dataclasses.schain_options import AllocationType, SchainOptions
from skale.types.node import NodeId, NodeWithChangeIp
from skale.types.schain import SchainHash, SchainName, SchainStructure
from web3.types import Wei

from core.redis_cache import hex_to_bytes
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)


def get_leaving_schains_for_node(skale: SkaleManager, node_id: NodeId) -> list[SchainStructure]:
    logger.info('Get leaving_history for node ...')
    leaving_schains = []
    leaving_history = skale.node_rotation.get_leaving_history(node_id)
    for leaving_schain in leaving_history:
        schain = skale.schains.get(leaving_schain['schain_id'])
        if skale.node_rotation.is_rotation_active(schain.name) and schain.name:
            schain.active = True
            leaving_schains.append(schain)
    logger.info(f'Got leaving sChains for the node: {leaving_schains}')
    return leaving_schains


def fetch_schains_to_monitor(skale: SkaleManager, node_id: NodeId) -> list[SchainStructure]:
    """
    Returns list of sChain dicts that admin should monitor (currently assigned + rotating).
    """
    logger.info('Fetching schains to monitor...')
    schains = skale.schains.schains_for_node(node_id)
    leaving_schains = get_leaving_schains_for_node(skale, node_id)
    schains.extend(leaving_schains)
    active_schains = list(filter(lambda schain: schain.active, schains))
    schains_holes = len(schains) - len(active_schains)
    logger.info(
        arguments_list_string(
            {
                'Node ID': node_id,
                'sChains on node': active_schains,
                'Number of sChains on node': len(active_schains),
                'Empty sChain structs': schains_holes,
            },
            'Monitoring sChains',
        )
    )
    return active_schains


def schain_structure_from_dict(d: dict[str, Any]) -> SchainStructure:
    opt = d['options']
    return SchainStructure(
        name=SchainName(d['name']),
        mainnet_owner=ChecksumAddress(d['mainnet_owner']),
        index_in_owner_list=int(d['index_in_owner_list']),
        part_of_node=int(d['part_of_node']),
        lifetime=int(d['lifetime']),
        start_date=int(d['start_date']),
        start_block=int(d['start_block']),
        deposit=Wei(int(d['deposit'])),
        index=int(d['index']),
        generation=int(d['generation']),
        originator=ChecksumAddress(d['originator']),
        schain_hash=SchainHash(hex_to_bytes(d['schain_hash'])),
        options=SchainOptions(
            multitransaction_mode=bool(opt['multitransaction_mode']),
            threshold_encryption=bool(opt['threshold_encryption']),
            allocation_type=AllocationType(opt['allocation_type']),
        ),
        active=bool(d['active']),
    )


def should_refresh_schains(
    skale: SkaleManager, node_id: NodeId, cached: list[SchainStructure]
) -> bool:
    current = skale.schains_internal.schain_hashes_for_node(node_id)
    cached_hashes = set(s.schain_hash for s in cached)
    return set(current) != cached_hashes


def fetch_connected_nodes(skale: SkaleManager, node_id: NodeId) -> list[NodeWithChangeIp]:
    logger.info('Fetching all connected nodes')
    node_ids = skale.schains_internal.connected_node_ids(node_id)
    return [skale.nodes.get_with_change_ip(node_id) for node_id in node_ids]
