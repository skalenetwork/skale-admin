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
from typing import Dict, List

from skale import Skale

from core.schains.firewall.entities import IpRange
from tools.notifications.messages import notify_balance

logger = logging.getLogger(__name__)

REQUIRED_BALANCE_WEI = 10 ** 17


def notify_if_not_enough_balance(skale: Skale, node_info: Dict) -> None:
    eth_balance_wei = skale.web3.eth.getBalance(skale.wallet.address)
    logger.info(f'Node account has {eth_balance_wei} WEI')
    balance_in_skl = skale.web3.fromWei(eth_balance_wei, 'ether')
    required_in_skl = skale.web3.fromWei(REQUIRED_BALANCE_WEI, 'ether')
    notify_balance(node_info, balance_in_skl, required_in_skl)


def get_sync_agent_ranges(skale: Skale) -> List[IpRange]:
    sync_agent_ranges = []
    rnum = skale.sync_manager.get_ip_ranges_number()
    for i in range(rnum):
        sync_agent_ranges.appned(skale.sync_manager.get_ip_range_by_index(i))
    return sync_agent_ranges
