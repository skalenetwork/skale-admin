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

import time

from tools.configs import MAX_ALLOWED_TIMESTAMP_DIFF
from tools.helper import post_request


def make_rpc_call(http_endpoint, method, params=[]) -> bool:
    return post_request(
        http_endpoint,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    )


def check_endpoint_alive(http_endpoint):
    res = make_rpc_call(http_endpoint, 'eth_blockNumber')
    return res and res.status_code == 200


def check_endpoint_blocks(http_endpoint):
    res = make_rpc_call(http_endpoint, 'eth_getBlockByNumber', ['latest', False])
    if res and res.json:
        latest_schain_timestamp_hex = res.json['result']['timestamp']
        latest_schain_timestamp = int(latest_schain_timestamp_hex, 16)
        admin_timestamp = int(time.time())
        return abs(latest_schain_timestamp - admin_timestamp) < MAX_ALLOWED_TIMESTAMP_DIFF
    return False
