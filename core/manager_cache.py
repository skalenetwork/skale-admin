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

from skale.types.node import NodeWithChangeIp
from skale.types.schain import SchainStructure

from core.firewall.base.types import IpRange
from core.firewall.utils import get_sync_agent_ranges
from core.manager_cache_helper import (
    fetch_connected_nodes,
    fetch_schains_to_monitor,
    schain_structure_from_dict,
    should_refresh_schains,
)
from core.redis_cache import CacheSpec, RedisCache, cached, json_bytes, json_obj

logger = logging.getLogger(__name__)


class ManagerCache(RedisCache):
    key_prefix = 'manager-cache:v1'

    def clear_dkg_timeout(self) -> None:
        logger.info('Clearing DKG timeout cache')
        self.clear('dkg_timeout')

    def clear_sync_ranges(self) -> None:
        logger.info('Clearing sync ranges cache')
        self.clear('sync_ranges')

    def clear_schains(self) -> None:
        logger.info('Clearing schains cache')
        self.clear('schains')

    def clear_nodes(self) -> None:
        logger.info('Clearing nodes cache')
        self.clear('nodes')

    def clear_all_fields(self) -> None:
        logger.info('Clearing all manager cache fields')
        self.clear_many(['dkg_timeout', 'sync_ranges', 'schains', 'nodes'])

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

    nodes: cached[list[NodeWithChangeIp]] = cached(
        CacheSpec[list[NodeWithChangeIp]](
            name='nodes',
            ttl=840,
            fetch=lambda self: fetch_connected_nodes(self.skale, self.node_id),
            ser=lambda nodes: json_bytes([n for n in nodes]),
            de=lambda raw: [x for x in json_obj(raw)],
        )
    )
