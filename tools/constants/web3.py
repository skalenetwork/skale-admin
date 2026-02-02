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

from eth_typing import HexAddress, HexStr

UNTRUSTED_PROVIDERS = ['infura.io', 'gateway.pokt.network']
NODE_REGISTER_CONFIRMATION_BLOCKS = 5

ZERO_ADDRESS = HexAddress(HexStr('0x0000000000000000000000000000000000000000'))

CACHE_TTL_POLICY = {
    'eth_call': 1,
    'eth_getCode': 30,
    'eth_getStorageAt': 30,
    'eth_chainId': 600,
    'eth_getBlockByNumber': 60,
    'eth_gasPrice': 5,
    'web3_clientVersion': 600,
}
