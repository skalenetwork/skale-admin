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

from ima_predeployed.generator import generate_abi
from skale import SkaleIma, SkaleManager

from tools.constants.ima import (
    _IMA_MAINNET_ABI_FILEPATH,
    _IMA_SCHAIN_ABI_FILEPATH,
    _MANAGER_ABI_FILEPATH,
)

logger = logging.getLogger(__name__)


def generate_ima_container_abis(skale: SkaleManager, skale_ima: SkaleIma) -> None:
    generate_manager_abi(skale)
    generate_ima_mainnet_abi(skale_ima)
    generate_ima_schain_abi()


def generate_manager_abi(skale: SkaleManager) -> None:
    logger.info(f'Going to generate a new ABI file for skale-manager ({_MANAGER_ABI_FILEPATH})')
    with open(_MANAGER_ABI_FILEPATH, 'w') as outfile:
        json.dump(skale._generate_legacy_abi(), outfile, indent=4)
    logger.info(f'New ABI file for skale-manager saved: {_MANAGER_ABI_FILEPATH}')


def generate_ima_mainnet_abi(skale_ima: SkaleIma) -> None:
    logger.info(f'Going to generate a new ABI file for mainnet IMA ({_IMA_MAINNET_ABI_FILEPATH})')
    with open(_IMA_MAINNET_ABI_FILEPATH, 'w') as outfile:
        json.dump(skale_ima._generate_legacy_abi(), outfile, indent=4)
    logger.info(f'New ABI file for mainnet IMA saved: {_IMA_MAINNET_ABI_FILEPATH}')


def generate_ima_schain_abi() -> None:
    logger.info(f'Going to generate a new ABI file for sChain IMA ({_IMA_SCHAIN_ABI_FILEPATH})')
    with open(_IMA_SCHAIN_ABI_FILEPATH, 'w') as outfile:
        json.dump(generate_abi(), outfile, indent=4)
    logger.info(f'New ABI file for sChain IMA saved: {_IMA_SCHAIN_ABI_FILEPATH}')
