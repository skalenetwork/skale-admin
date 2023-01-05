#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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

import json
import logging
import requests

from skale import SkaleManager
from skale.schain_config.rotation_history import get_previous_schain_groups, get_new_nodes_list

from core.schain.config.helper import get_skaled_http_address

logger = logging.getLogger(__name__)


def set_exit_request(schain_name: str, timestamp: int) -> None:
    logger.info('sChain %s restart scheduled for %d', schain_name, timestamp)
    url = get_skaled_http_address(schain_name)
    _send_rotation_request(url, timestamp)


def _send_rotation_request(url, timestamp):
    logger.info(f'Send rotation request: {timestamp}')
    headers = {'content-type': 'application/json'}
    data = {
        'finishTime': timestamp
    }
    call_data = {
        "id": 0,
        "jsonrpc": "2.0",
        "method": "setSchainExitTime",
        "params": data,
    }
    response = requests.post(
        url=url,
        data=json.dumps(call_data),
        headers=headers,
    ).json()
    if response.get('error'):
        raise Exception(response['error']['message'])


def get_schain_public_key(skale, schain_name):
    group_idx = skale.schains.name_to_id(schain_name)
    raw_public_key = skale.key_storage.get_previous_public_key(group_idx)
    public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    if public_key_array == ['0', '0', '1', '0']:  # zero public key
        raw_public_key = skale.key_storage.get_common_public_key(group_idx)
        public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    return ':'.join(map(str, public_key_array))


def get_new_nodes_for_schain(
    skale: SkaleManager,
    name: str,
    leaving_node: int
) -> list:
    node_groups = get_previous_schain_groups(
        skale=skale,
        schain_name=name,
        leaving_node_id=leaving_node,
        include_keys=False
    )
    return get_new_nodes_list(
        skale=skale,
        name=name,
        node_groups=node_groups
    )
