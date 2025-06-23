#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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

import os
from eth_typing import HexAddress, HexStr

from tools.configs import NODE_DATA_PATH
from tools.exceptions import MissingEnvVariable

ENDPOINT = os.getenv('ENDPOINT')
BOOT_ENDPOINT = os.getenv('BOOT_ENDPOINT')

UNTRUSTED_PROVIDERS = ['infura.io', 'gateway.pokt.network']
MANAGER_CONTRACTS = os.getenv('MANAGER_CONTRACTS')
MIRAGE_CONTRACTS = os.getenv('MIRAGE_CONTRACTS')
STATE_FILENAME = os.getenv('STATE_FILENAME')
STATE_BASE_PATH = os.path.join(NODE_DATA_PATH, 'eth-state')
STATE_FILEPATH = None if not STATE_FILENAME else os.path.join(STATE_BASE_PATH, STATE_FILENAME)

NODE_REGISTER_CONFIRMATION_BLOCKS = 5

ZERO_ADDRESS = HexAddress(HexStr('0x0000000000000000000000000000000000000000'))


def endpoint() -> str:
    if not ENDPOINT:
        raise MissingEnvVariable('ENDPOINT is not set.')
    return ENDPOINT


def boot_endpoint() -> str:
    if not BOOT_ENDPOINT:
        raise MissingEnvVariable('BOOT_ENDPOINT is not set.')
    return BOOT_ENDPOINT


def manager_contracts() -> str:
    if not MANAGER_CONTRACTS:
        raise MissingEnvVariable('MANAGER_CONTRACTS environment variable is not set.')
    return MANAGER_CONTRACTS


def mirage_contracts() -> str:
    if not MIRAGE_CONTRACTS:
        raise MissingEnvVariable('MIRAGE_CONTRACTS environment variable is not set.')
    return MIRAGE_CONTRACTS
