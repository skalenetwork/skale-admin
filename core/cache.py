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
from typing import TypedDict

from skale import SkaleManager
from skale.types.node import NodeId
from skale.types.schain import SchainStructure

from core.firewall.base.types import IpRange
from core.firewall.utils import get_sync_agent_ranges
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)


def get_leaving_schains_for_node(skale: SkaleManager, node_id: NodeId) -> list:
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


class AdminCacheDict(TypedDict):
    sync_ranges: list[IpRange]
    dkg_timeout: int
    schains: list[SchainStructure]


class AdminCache:
    def __init__(self, skale: SkaleManager, node_id: NodeId):
        self._cache: AdminCacheDict = {
            'dkg_timeout': skale.constants_holder.get_dkg_timeout(),
            'sync_ranges': get_sync_agent_ranges(skale),
            'schains': fetch_schains_to_monitor(skale, node_id),
            # 'nodes'
        }

    def refresh(self, skale: SkaleManager, node_id: NodeId) -> None:
        self.refresh_dkg_timeout(skale)
        self.refresh_sync_ranges(skale)
        self.refresh_schains(skale, node_id)

    @property
    def dkg_timeout(self) -> int:
        return self._cache['dkg_timeout']

    @property
    def sync_ranges(self) -> list[IpRange]:
        return self._cache['sync_ranges']

    @property
    def schains(self) -> list[SchainStructure]:
        return self._cache['schains']

    def refresh_dkg_timeout(self, skale: SkaleManager) -> None:
        dkg_timeout = skale.constants_holder.get_dkg_timeout()
        self._cache['dkg_timeout'] = dkg_timeout

    def refresh_sync_ranges(self, skale: SkaleManager) -> None:
        rnum = skale.sync_manager.get_ip_ranges_number()
        if rnum != len(self._cache['sync_ranges']):
            allowed_ranges = get_sync_agent_ranges(skale)
            self._cache['sync_ranges'] = allowed_ranges
        else:
            logger.info('Sync ranges in cache are up to date')

    def refresh_schains(self, skale: SkaleManager, node_id: NodeId) -> None:
        schain_hashes = skale.schains_internal.get_schain_hashes_for_node(node_id)
        cached_hashes = [schain.schain_hash for schain in self._cache['schains']]
        if set(schain_hashes) != set(cached_hashes):
            self._cache['schains'] = fetch_schains_to_monitor(skale, node_id)
        else:
            logger.info('Schains in cache are up to date')
