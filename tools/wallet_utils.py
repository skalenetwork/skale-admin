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

import logging


from redis import Redis
from skale.utils.web3_utils import init_web3
from skale.wallets import BaseWallet, RedisWalletAdapter, SgxWallet
from skale.wallets.web3_wallet import to_checksum_address

from tools.configs import (
    DEFAULT_POOL,
    SGX_CERTIFICATES_FOLDER,
    SGX_SERVER_URL
)
from tools.configs.web3 import ENDPOINT
from tools.resources import rs as grs

logger = logging.getLogger(__name__)

# todo: move to smart contracts
DEPOSIT_AMOUNT_ETH = 0.2
DEPOSIT_AMOUNT_ETH_WEI = int(DEPOSIT_AMOUNT_ETH * (10 ** 18))


def wallet_with_balance(skale):  # todo: move to the skale.py
    address = skale.wallet.address
    eth_balance_wei = skale.web3.eth.get_balance(address)
    return {
        'address': to_checksum_address(address),
        'eth_balance_wei': eth_balance_wei,
        'skale_balance_wei': 0,
        'eth_balance': str(skale.web3.from_wei(eth_balance_wei, 'ether')),
        'skale_balance': '0'
    }


def check_required_balance(skale):  # todo: move to the skale.py
    balances = wallet_with_balance(skale)
    return int(balances['eth_balance_wei']) >= DEPOSIT_AMOUNT_ETH_WEI


def init_wallet(
    node_config,
    rs: Redis = grs,
    pool: str = DEFAULT_POOL
) -> BaseWallet:
    web3 = init_web3(ENDPOINT)
    sgx_wallet = SgxWallet(
        web3=web3,
        sgx_endpoint=SGX_SERVER_URL,
        key_name=node_config.sgx_key_name,
        path_to_cert=SGX_CERTIFICATES_FOLDER
    )
    return RedisWalletAdapter(rs, pool, sgx_wallet)
