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

logger = logging.getLogger(__name__)

# todo: move to smart contracts
DEPOSIT_AMOUNT_SKL = 100
DEPOSIT_AMOUNT_ETH = 0.2

DEPOSIT_AMOUNT_SKL_WEI = DEPOSIT_AMOUNT_SKL * (10 ** 18)
DEPOSIT_AMOUNT_ETH_WEI = int(DEPOSIT_AMOUNT_ETH * (10 ** 18))


def wallet_with_balance(skale):  # todo: move to the skale.py
    address = skale.wallet.address
    eth_balance_wei = skale.web3.eth.getBalance(address)
    skale_balance_wei = skale.token.get_balance(address)
    return {
        'address': address,
        'eth_balance_wei': eth_balance_wei,
        'skale_balance_wei': skale_balance_wei,
        'eth_balance': str(skale.web3.fromWei(eth_balance_wei, 'ether')),
        'skale_balance': str(skale.web3.fromWei(skale_balance_wei, 'ether'))
    }


def check_required_balance(skale):  # todo: move to the skale.py
    balances = wallet_with_balance(skale)
    return int(balances['eth_balance_wei']) >= DEPOSIT_AMOUNT_ETH_WEI and int(balances[
        'skale_balance_wei']) >= DEPOSIT_AMOUNT_SKL_WEI


def get_required_balance():  # todo: move to the skale.py, request valuest from skale-manager
    return {'eth_balance': DEPOSIT_AMOUNT_ETH, 'skale_balance': DEPOSIT_AMOUNT_SKL}
