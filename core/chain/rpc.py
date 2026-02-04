#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
from typing import cast

from requests import Response

from core.chain.runner import is_container_exists, is_container_running, restart_container
from core.chain.status import SkaledStatus
from core.redis.chain_record import ChainRecord
from core.types.chain import ChainName
from tools.constants.containers import SKALED_CONTAINER
from tools.constants.schains import (
    DEFAULT_RPC_CHECK_TIMEOUT,
    MAX_SCHAIN_FAILED_RPC_COUNT,
    RPC_CHECK_TIMEOUT_STEP,
)
from tools.docker_utils import DockerUtils
from tools.helper import post_request
from tools.settings import get_settings
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)

ALLOWED_TIMESTAMP_DIFF = 120


def handle_failed_skaled_rpc(
    chain_name: ChainName,
    chain_record: ChainRecord | SChainRecord,
    skaled_status: SkaledStatus,
    dutils: DockerUtils | None = None,
):
    dutils = dutils or DockerUtils()
    logger.info(f'Monitoring RPC for chain {chain_name}')

    if not is_container_exists(chain_name, dutils=dutils):
        logger.warning('RPC monitor failed: container does not exist')
        return

    if not is_container_running(chain_name, dutils=dutils):
        logger.warning('RPC monitor failed: container is not running')
        return

    if skaled_status.exit_time_reached:
        logger.info('Skipping RPC monitor: exit time reached')
        skaled_status.log()
        chain_record.set_failed_rpc_count(0)
        return

    if skaled_status.downloading_snapshot:
        logger.info('Skipping RPC monitor: downloading snapshot')
        skaled_status.log()
        chain_record.set_failed_rpc_count(0)
        return

    if not skaled_status.subsystem_running or not skaled_status.subsystem_running['Rpc']:
        logger.info('Skipping RPC monitor: Rpc has not been initialized')
        skaled_status.log()
        chain_record.set_failed_rpc_count(0)

    rpc_stuck = cast(int, chain_record.failed_rpc_count) > MAX_SCHAIN_FAILED_RPC_COUNT
    logger.info(
        'Chain %s, rpc stuck: %s, failed_rpc_count: %d, restart_count: %d',
        chain_name,
        rpc_stuck,
        chain_record.failed_rpc_count,
        chain_record.restart_count,
    )
    if rpc_stuck:
        st = get_settings()
        if cast(int, chain_record.restart_count) < st.max_skaled_restart_count:
            logger.info(f'Chain {chain_name}: restarting container')
            restart_container(SKALED_CONTAINER, chain_name, dutils=dutils)
            chain_record.set_restart_count(cast(int, chain_record.restart_count) + 1)
        else:
            logger.warning(f'Chain {chain_name}: max restart count exceeded')
        chain_record.set_failed_rpc_count(0)
    else:
        chain_record.set_failed_rpc_count(cast(int, chain_record.failed_rpc_count) + 1)


def make_rpc_call(http_endpoint, method, params=None, timeout=None) -> Response | None:
    params = params or []
    return post_request(
        http_endpoint,
        json={'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1},
        timeout=timeout,
    )


def get_endpoint_alive_check_timeout(failed_rpc_count: int) -> int:
    if not failed_rpc_count:
        return DEFAULT_RPC_CHECK_TIMEOUT
    return DEFAULT_RPC_CHECK_TIMEOUT + failed_rpc_count * RPC_CHECK_TIMEOUT_STEP


def check_endpoint_alive(http_endpoint: str, timeout=None) -> bool:
    timeout = timeout or DEFAULT_RPC_CHECK_TIMEOUT
    res = make_rpc_call(http_endpoint, 'eth_blockNumber', timeout=timeout)
    return (res is not None and res.status_code == 200) or False


def check_endpoint_blocks(http_endpoint: str) -> bool:
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
