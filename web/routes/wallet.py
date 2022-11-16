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

from web.helper import (
    construct_ok_response,
    construct_err_response,
    get_api_url,
    g_skale
)
from tools.wallet_utils import wallet_with_balance

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'wallet'


wallet_bp = Blueprint(BLUEPRINT_NAME, __name__)


@wallet_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
@g_skale
def info():
    logger.debug(request)
    res = wallet_with_balance(g.skale)
    return construct_ok_response(data=res)


@wallet_bp.route(get_api_url(BLUEPRINT_NAME, 'send-eth'), methods=['POST'])
@g_skale
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
        logger.info(
            f'Sending {eth_amount} wei to {address}'
        )
        send_eth_(g.skale.web3, g.skale.wallet, address, eth_amount)
    except Exception:
        logger.exception('Funds were not sent due to error')
        return construct_err_response(msg='Funds sending failed')
    return construct_ok_response()
