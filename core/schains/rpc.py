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

import json
import logging
import time

from tools.configs import ALLOWED_TIMESTAMP_DIFF
from tools.configs.schains import DEFAULT_RPC_CHECK_TIMEOUT, RPC_CHECK_TIMEOUT_STEP
from tools.helper import post_request


logger = logging.getLogger(__name__)


def make_rpc_call(http_endpoint, method, params=None, timeout=None) -> bool:
    params = params or []
    return post_request(
        http_endpoint,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=timeout
    )


def get_endpoint_alive_check_timeout(failed_rpc_count):
    if not failed_rpc_count:
        return DEFAULT_RPC_CHECK_TIMEOUT
    return DEFAULT_RPC_CHECK_TIMEOUT + failed_rpc_count * RPC_CHECK_TIMEOUT_STEP


def check_endpoint_alive(http_endpoint, timeout=None):
    timeout = timeout or DEFAULT_RPC_CHECK_TIMEOUT
    res = make_rpc_call(http_endpoint, 'eth_blockNumber', timeout=timeout)
    return (res and res.status_code == 200) or False


def check_endpoint_blocks(http_endpoint):
    res = make_rpc_call(http_endpoint, 'eth_getBlockByNumber', ['latest', False])
    healthy = False
    if res:
        try:
            res_data = res.json()
            latest_schain_timestamp_hex = res_data['result']['timestamp']
            latest_schain_timestamp = int(latest_schain_timestamp_hex, 16)
            admin_timestamp = int(time.time())
            healthy = abs(latest_schain_timestamp - admin_timestamp) < ALLOWED_TIMESTAMP_DIFF
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning('Failed to parse response, error: %s', e)
    else:
        logger.warning('Empty response from skaled')
    return healthy
