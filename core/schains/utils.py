#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2020 SKALE Labs
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

from tools.notifications.messages import notify_balance
from tools.configs import REQUIRED_BALANCE_WEI

logger = logging.getLogger(__name__)


def notify_if_not_enough_balance(skale, node_info):
    required = skale.web3.fromWei(REQUIRED_BALANCE_WEI, 'ether')
    logger.info(f'Checking if node account has required {required} eth')
    eth_balance_wei = skale.web3.eth.getBalance(skale.wallet.address)
    logger.info(f'Node account has {eth_balance_wei} WEI')
    balance = skale.web3.fromWei(eth_balance_wei, 'ether')
    notify_balance(node_info, balance, required)
