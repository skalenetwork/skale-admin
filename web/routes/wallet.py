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

from flask import Blueprint, request
from skale.utils.account_tools import send_ether

from web.helper import construct_ok_response, construct_err_response
from tools.wallet_utils import wallet_with_balance

logger = logging.getLogger(__name__)


def construct_wallet_bp(skale):
    wallet_bp = Blueprint('wallet', __name__)

    @wallet_bp.route('/load-wallet', methods=['GET'])
    def load_wallet():
        logger.debug(request)
        res = wallet_with_balance(skale)
        return construct_ok_response(data=res)

    @wallet_bp.route('/send-eth', methods=['POST'])
    def send_eth():
        logger.debug(request)
        address = request.json.get('address')
        eth_amount = request.json.get('amount')
        if not address:
            return construct_err_response('Address is empty')
        if not eth_amount:
            return construct_err_response('Amount is empty')
        try:
            send_ether(skale.web3, skale.wallet, address, eth_amount)
        except Exception as err:
            logger.error('Funds were not sent due to error', exc_info=err)
            construct_err_response(['Funds sending failed'])
        return construct_ok_response('Funds were sent successfully')

    return wallet_bp
