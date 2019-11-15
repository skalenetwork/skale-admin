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
from tools.configs import LOCAL_WALLET_FILEPATH
from tools.config_storage import ConfigStorage

logger = logging.getLogger(__name__)

# todo: move to smart contracts
DEPOSIT_AMOUNT_SKL = 100
DEPOSIT_AMOUNT_ETH = 0.2

DEPOSIT_AMOUNT_SKL_WEI = DEPOSIT_AMOUNT_SKL * (10 ** 18)
DEPOSIT_AMOUNT_ETH_WEI = int(DEPOSIT_AMOUNT_ETH * (10 ** 18))

class LocalWallet:  # todo: refactor
    def __init__(self, skale, rpc_wallet):
        self.skale = skale
        self.rpc_wallet = rpc_wallet
        #self.skale.web3.eth.enable_unaudited_features()  # todo: deal with this

    def generate_local_wallet(self, password=None, extra_entropy=''):
        return {'address': self.rpc_wallet.address}

    def get_or_generate(self):
        return self.generate_local_wallet()

    def get_full(self):
        local_wallet_config = ConfigStorage(LOCAL_WALLET_FILEPATH)
        return local_wallet_config.get()

    def get(self):
        return self.generate_local_wallet()

    def get_with_balance(self):
        wallet = self.get()
        if not wallet.get('address', None):
            return wallet

        eth_balance_wei = self.skale.web3.eth.getBalance(wallet['address'])
        skale_balance_wei = self.skale.token.get_balance(wallet['address'])

        logging.debug(f'get_with_balance raw info: address: {wallet["address"]}, eth_balance_wei: {eth_balance_wei}, skale_balance_wei: {skale_balance_wei}')

        wallet['eth_balance_wei'] = str(eth_balance_wei)
        wallet['skale_balance_wei'] = str(skale_balance_wei)
        wallet['eth_balance'] = str(self.skale.web3.fromWei(eth_balance_wei, 'ether'))
        wallet['skale_balance'] = str(self.skale.web3.fromWei(skale_balance_wei, 'ether'))

        return wallet

    def check_required_balance(self):
        wallet = self.get_with_balance()
        return int(wallet['eth_balance_wei']) >= DEPOSIT_AMOUNT_ETH_WEI and int(wallet[
            'skale_balance_wei']) >= DEPOSIT_AMOUNT_SKL_WEI

    def get_required_balance(self):
        return {'eth_balance': DEPOSIT_AMOUNT_ETH, 'skale_balance': DEPOSIT_AMOUNT_SKL}