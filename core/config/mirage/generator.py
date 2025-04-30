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
from dataclasses import dataclass

from core.config.base_config import MirageConfig, SChainBaseConfig
from core.config.mirage.schain_info import MirageSChainInfo
from core.config.mirage.node_info import MirageCurrentNodeInfo
from core.config.precompiled import get_precompiled_contracts_mirage
from core.config.schain.static_params import get_static_schain_info

from tools.configs import MIRAGE_CHAIN_NAME
from tools.configs.schains import (
    MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH,
    MAX_CONSENSUS_STORAGE_INF_VALUE,
)


logger = logging.getLogger(__name__)


@dataclass
class MirageSkaleConfig:
    node_info: MirageCurrentNodeInfo
    schain_info: MirageSChainInfo

    def to_dict(self):
        return {
            # 'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


def generate_mirage_config_with_manager() -> None:
    """Will be implemented in the future"""
    pass


def get_mirage_chain_id() -> str:
    return '0x3A6'  # TODO: Replace with actual logic to get the chain ID (or move to config file)


def generate_mirage_config(nodes: list, node_groups: dict) -> MirageConfig:
    logger.info('Generating Mirage config...')
    base_config = SChainBaseConfig(MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH)

    chain_id = get_mirage_chain_id()
    chain_id_int = int(chain_id, 16)

    dynamic_params = {'chainID': chain_id}
    accounts = get_precompiled_contracts_mirage()

    static_schain_info = get_static_schain_info(MIRAGE_CHAIN_NAME)

    contract_storage_limit = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value
    db_storage_limit = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value
    max_consensus_storage_bytes = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value

    schain_info = MirageSChainInfo(
        schain_id=chain_id_int,
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        max_consensus_storage_bytes=max_consensus_storage_bytes,
        node_groups=node_groups,
        nodes=nodes,  # TODOA
        static_schain_info=static_schain_info,
    )

    current_node_info = MirageCurrentNodeInfo(test_value=0)  # TODOA

    skale_config = MirageSkaleConfig(schain_info=schain_info, node_info=current_node_info)

    return MirageConfig(
        seal_engine=base_config.config['sealEngine'],
        params={**base_config.config['params'], **dynamic_params},
        unddos=base_config.config['unddos'],
        genesis=base_config.config['genesis'],
        accounts=accounts,
        skale_config=skale_config,
    )
