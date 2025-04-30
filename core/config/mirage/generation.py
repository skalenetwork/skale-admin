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

from dataclasses import dataclass

from core.config.base_config import MirageConfig, SChainBaseConfig
from core.config.precompiled import get_precompiled_contracts_mirage
from tools.configs.schains import MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH


@dataclass
class MirageSkaleConfig:
    test: str

    def to_dict(self):
        return {'test': self.test}


def generate_mirage_config_with_manager() -> None:
    """Will be implemented in the future"""
    pass


def get_mirage_chain_id() -> str:
    return '0x3A6'  # TODO: Replace with actual logic to get the chain ID (or move to config file)


def generate_mirage_config() -> MirageConfig:
    base_config = SChainBaseConfig(MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH)

    dynamic_params = {'chainID': get_mirage_chain_id()}
    accounts = get_precompiled_contracts_mirage()

    skale_config = MirageSkaleConfig(test='test')

    return MirageConfig(
        seal_engine=base_config.config['sealEngine'],
        params={**base_config.config['params'], **dynamic_params},
        unddos=base_config.config['unddos'],
        genesis=base_config.config['genesis'],
        accounts=accounts,
        skale_config=skale_config,
    )
