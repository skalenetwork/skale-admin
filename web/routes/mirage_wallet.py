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

from flask import Blueprint, g, request
from skale.utils.account_tools import send_eth as send_eth_
from skale.utils.web3_utils import to_checksum_address

from web.helper import construct_err_response, construct_ok_response, g_mirage, get_api_url

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'wallet'


wallet_bp = Blueprint(BLUEPRINT_NAME, __name__)


def wallet_with_balance(mirage):
    address = mirage.wallet.address
    mirage_balance_wei = mirage.web3.eth.get_balance(address)
    return {
        'address': to_checksum_address(address),
        'mirage_balance_wei': mirage_balance_wei,
        'mirage_balance': str(mirage.web3.from_wei(mirage_balance_wei, 'ether')),
    }


@wallet_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
@g_mirage
def info():
    logger.debug(request)
    res = wallet_with_balance(g.mirage)
    return construct_ok_response(data=res)


@wallet_bp.route(get_api_url(BLUEPRINT_NAME, 'send-eth'), methods=['POST'])
@g_mirage
def send_eth():
    logger.debug(request)
    raw_address = request.json.get('address')
    eth_amount = request.json.get('amount')
    if not raw_address:
        return construct_err_response('Address is empty')
    if not eth_amount:
        return construct_err_response('Amount is empty')
    try:
        address = to_checksum_address(raw_address)
        logger.info('Sending %s wei to %s', eth_amount, address)
        send_eth_(g.mirage.web3, g.mirage.wallet, address, eth_amount)
    except Exception:
        logger.exception('Funds were not sent due to error')
        return construct_err_response(msg='Funds sending failed')
    return construct_ok_response()
