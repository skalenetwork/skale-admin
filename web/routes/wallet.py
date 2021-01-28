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
from decimal import Decimal

from flask import Blueprint, request
from skale.transactions.tools import send_eth_with_skale
from skale.utils.web3_utils import to_checksum_address
from web3 import Web3

from web.helper import construct_ok_response, construct_err_response
from tools.helper import init_default_skale
from tools.wallet_utils import wallet_with_balance

logger = logging.getLogger(__name__)


def construct_wallet_bp():
    wallet_bp = Blueprint('wallet', __name__)

    @wallet_bp.route('/load-wallet', methods=['GET'])
    def load_wallet():
        logger.debug(request)
        skale = init_default_skale()
        res = wallet_with_balance(skale)
        return construct_ok_response(data=res)

    @wallet_bp.route('/api/send-eth', methods=['POST'])
    def send_eth():
        logger.debug(request)
        raw_address = request.json.get('address')
        eth_amount = request.json.get('amount')
        gas_limit = request.json.get('gas_limit', None)
        gas_price = request.json.get('gas_price', None)
        if gas_price is not None:
            gas_price = Web3.toWei(Decimal(gas_price), 'gwei')
        wei_amount = Web3.toWei(eth_amount, 'ether')
        if not raw_address:
            return construct_err_response('Address is empty')
        if not eth_amount:
            return construct_err_response('Amount is empty')
        try:
            address = to_checksum_address(raw_address)
            logger.info(
                f'Sending {eth_amount} wei to {address} with '
                f'gas_price: {gas_price} Wei, '
                f'gas_limit: {gas_limit}'
            )
            skale = init_default_skale()
            send_eth_with_skale(skale, address, wei_amount,
                                gas_limit=gas_limit, gas_price=gas_price)
        except Exception:
            logger.exception('Funds were not sent due to error')
            return construct_err_response(msg='Funds sending failed')
        return construct_ok_response()

    return wallet_bp
