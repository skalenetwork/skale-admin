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

import logging

from core.ima.schain import copy_schain_ima_abi
from core.schains.volume import is_volume_exists
from core.schains.runner import (
    is_schain_container_failed,
    restart_container,
    run_schain_container,
    is_container_exists
)
from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER
)
from tools.docker_utils import DockerUtils


logger = logging.getLogger(__name__)


def monitor_schain_container(
    schain,
    schain_record,
    public_key=None,
    start_ts=None,
    volume_required=True,
    dutils=None
):
    dutils = dutils or DockerUtils()
    schain_name = schain['name']
    logger.info(f'Monitoring container for sChain {schain_name}')
    if volume_required and not is_volume_exists(schain_name, dutils=dutils):
        logger.error(f'Data volume for sChain {schain_name} does not exist')
        return

    if not is_container_exists(schain_name, dutils=dutils):
        logger.info(f'SChain {schain_name}: container doesn\'t exits')
        run_schain_container(
            schain=schain,
            public_key=public_key,
            start_ts=start_ts,
            dutils=dutils
        )
        return

    bad_exit = is_schain_container_failed(schain_name, dutils=dutils)
    logger.info(
        'SChain %s, failed: %s, %d',
        schain_name,
        bad_exit,
        schain_record.restart_count
    )
    if bad_exit:
        if schain_record.restart_count < MAX_SCHAIN_RESTART_COUNT:
            logger.info(f'SChain {schain_name}: restarting container')
            restart_container(SCHAIN_CONTAINER, schain, dutils=dutils)
            schain_record.set_restart_count(schain_record.restart_count + 1)
            schain_record.set_failed_rpc_count(0)
        else:
            logger.warning(f'SChain {schain_name}: max restart count exceeded')


def monitor_ima_container(skale_ima, schain, dutils=None):
    dutils = dutils or DockerUtils()
    mainnet_chain_id = skale_ima.web3.eth.chainId
    # todo: add IMA version check
    if skale_ima.linker.has_schain(schain['name']):
        copy_schain_ima_abi(schain['name'])
        monitor_ima_container(schain, mainnet_chain_id, dutils=dutils)
    else:
        logger.warning(f'sChain {schain["name"]} is not registered in IMA')
