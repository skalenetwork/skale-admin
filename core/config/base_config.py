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

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Dict, TYPE_CHECKING

from tools.helper import read_json

if TYPE_CHECKING:
    from core.config.schain.skale_section import SkaleConfig
    from core.config.mirage.generation import MirageSkaleConfig


logger = logging.getLogger(__name__)


@dataclass
class BaseConfig:
    seal_engine: str
    params: Dict
    unddos: Dict
    genesis: Dict
    accounts: Dict
    skale_config: SkaleConfig | MirageSkaleConfig

    def to_dict(self):
        return {
            'sealEngine': self.seal_engine,
            'params': self.params,
            'unddos': self.unddos,
            'genesis': self.genesis,
            'accounts': self.accounts,
            'skaleConfig': self.skale_config.to_dict(),
        }


@dataclass
class SChainConfig(BaseConfig):
    skale_config: SkaleConfig


@dataclass
class MirageConfig(BaseConfig):
    skale_config: MirageSkaleConfig


class NoBaseConfigError(Exception):
    pass


class SChainBaseConfig:
    """Wrapper for the static part of sChain config"""

    def __init__(self, base_config_path):
        self._base_config_path = base_config_path
        self.read()

    def read(self):
        logger.debug(f'Reading sChain base config: {self._base_config_path}')
        try:
            self.config = read_json(self._base_config_path)
        except Exception as err:
            raise NoBaseConfigError(err)
