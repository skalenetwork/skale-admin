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

import json
import logging
from typing import Any

from eth_typing import ChecksumAddress
from skale import SkaleManager
from skale.dataclasses.schain_options import AllocationType, SchainOptions
from skale.types.node import NodeId
from skale.types.schain import SchainHash, SchainName, SchainStructure
from web3.types import Wei

from core.firewall.base.types import IpRange
from core.firewall.utils import get_sync_agent_ranges
from core.redis_cache import CacheSpec, RedisCache, cached, hex_to_bytes, json_bytes, json_obj
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
    schains = skale.schains.get_schains_for_node(node_id)
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
    current = skale.schains_internal.get_schain_hashes_for_node(node_id)
    cached_hashes = [s.schain_hash for s in cached]
    return set(current) != set(cached_hashes)


class ManagerCache(RedisCache):
    key_prefix = 'manager-cache:v1'

    def should_refresh_schains(self, cached_schains: list[SchainStructure]) -> bool:
        current = self.skale.schains_internal.get_schain_hashes_for_node(self.node_id)
        cached = [s.schain_hash for s in cached_schains]
        return set(current) != set(cached)

    dkg_timeout: cached[int] = cached(
        CacheSpec[int](
            'dkg_timeout',
            3600,
            lambda self: self.skale.constants_holder.get_dkg_timeout(),
            lambda dkg_timeout: str(dkg_timeout).encode(),
            lambda rb: int(rb.decode()),
        )
    )

    sync_ranges: cached[list[IpRange]] = cached(
        CacheSpec[list[IpRange]](
            'sync_ranges',
            3600,
            lambda self: get_sync_agent_ranges(self.skale),
            ser=lambda ranges: json.dumps(
                [{'start': r.start_ip, 'end': r.end_ip} for r in ranges], separators=(',', ':')
            ).encode(),
            de=lambda rb: [IpRange(d['start'], d['end']) for d in json.loads(rb.decode())],
        )
    )

    schains: cached[list[SchainStructure]] = cached(
        CacheSpec[list[SchainStructure]](
            name='schains',
            ttl=1800,
            fetch=lambda self: fetch_schains_to_monitor(self.skale, self.node_id),
            ser=lambda schains: json_bytes([s.to_dict() for s in schains]),
            de=lambda raw: [schain_structure_from_dict(x) for x in json_obj(raw)],
            refresh_if=lambda self, cached: should_refresh_schains(
                self.skale, self.node_id, cached
            ),
        )
    )
