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
from tools.configs import CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME

IMA_ENDPOINT = os.environ['IMA_ENDPOINT']

PROXY_ABI_FILENAME = 'proxy.json'
MAINNET_PROXY_PATH = os.path.join(CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME)

PRECOMPILED_IMA_CONTRACTS = {
    'skale_features': {
        'filename': 'SkaleFeatures'
    },
    'lock_and_data_for_schain': {
        'filename': 'LockAndDataForSchain'
    },
    'eth_erc20': {
        'filename': 'EthERC20'
    },
    'token_manager': {
        'filename': 'TokenManager'
    },
    'lock_and_data_for_schain_erc20': {
        'filename': 'LockAndDataForSchainERC20'
    },
    'erc20_module_for_schain': {
        'filename': 'ERC20ModuleForSchain'
    },
    'lock_and_data_for_schain_erc721': {
        'filename': 'LockAndDataForSchainERC721'
    },
    'erc721_module_for_schain': {
        'filename': 'ERC721ModuleForSchain'
    },
    'token_factory': {
        'filename': 'TokenFactory'
    },
    'message_proxy_chain': {
        'filename': 'MessageProxyForSchain'
    }
}
