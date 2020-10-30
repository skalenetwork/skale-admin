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

from skale.wallets.sgx_queue_wallet import SgxQueueWallet
from skale.wallets.web3_wallet import to_checksum_address
from skale.utils.web3_utils import init_web3

from tools.configs import REDIS_URI, SGX_SERVER_URL
from tools.configs.web3 import ENDPOINT

logger = logging.getLogger(__name__)

# todo: move to smart contracts
DEPOSIT_AMOUNT_ETH = 0.2
DEPOSIT_AMOUNT_ETH_WEI = int(DEPOSIT_AMOUNT_ETH * (10 ** 18))


def wallet_with_balance(skale):  # todo: move to the skale.py
    address = skale.wallet.address
    eth_balance_wei = skale.web3.eth.getBalance(address)
    return {
        'address': to_checksum_address(address),
        'eth_balance_wei': eth_balance_wei,
        'skale_balance_wei': 0,
        'eth_balance': str(skale.web3.fromWei(eth_balance_wei, 'ether')),
        'skale_balance': '0'
    }


def check_required_balance(skale):  # todo: move to the skale.py
    balances = wallet_with_balance(skale)
    return int(balances['eth_balance_wei']) >= DEPOSIT_AMOUNT_ETH_WEI


def init_wallet(channel: str, key_name: str = None) -> SgxQueueWallet:
    web3 = init_web3(ENDPOINT)
    return SgxQueueWallet(
        SGX_SERVER_URL,
        web3,
        channel=channel,
        key_name=key_name,
        redis_uri=REDIS_URI
    )
