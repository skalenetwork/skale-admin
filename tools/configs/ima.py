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
from tools.configs import CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME, CONFIG_FOLDER

IMA_ENDPOINT = os.environ['IMA_ENDPOINT']
MAINNET_IMA_ABI_FILEPATH = os.path.join(CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME)

DISABLE_IMA = os.getenv('DISABLE_IMA') == 'True'

PROXY_ABI_FILENAME = 'proxy.json'

IMA_DATA_FILENAME = 'ima_data.json'
IMA_DATA_FILEPATH = os.path.join(CONFIG_FOLDER, IMA_DATA_FILENAME)


SCHAIN_IMA_CONTRACTS = {
    'skale_features': {
        'filename': 'SkaleFeatures'
    },
    'token_manager_eth': {
        'filename': 'TokenManagerEth'
    },
    'token_manager_erc20': {
        'filename': 'TokenManagerERC20'
    },
    'token_manager_erc721': {
        'filename': 'TokenManagerERC721'
    },
    'message_proxy_chain': {
        'filename': 'MessageProxyForSchain'
    },
    'token_manager_linker': {
        'filename': 'TokenManagerLinker'
    },
    'community_locker': {
        'filename': 'CommunityLocker'
    },
    'eth_erc20': {
        'filename': 'EthERC20'
    }
}


MAINNET_IMA_CONTRACTS = {
    'message_proxy_mainnet': {
        'filename': 'MessageProxyForMainnet'
    },
    'linker': {
        'filename': 'Linker'
    },
    'deposit_box_eth': {
        'filename': 'DepositBoxEth'
    },
    'deposit_box_erc20': {
        'filename': 'DepositBoxERC20'
    },
    'deposit_box_erc721': {
        'filename': 'DepositBoxERC721'
    }
}
