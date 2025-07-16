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
from time import sleep

from skale.types.dkg import Status

from core.dkg.utils import DKGKeyGenerationError
from core.dkg.fair.utils import (
    generate_bls_keys,
    init_dkg_client,
    DkgError,
    broadcast_and_check_data,
    check_dkg_id_with_exception,
    BROADCAST_DATA_SEARCH_SLEEP,
    send_alright_and_wait_for_others,
)
from core.dkg.structures import DKGResult, DKGStatus

logger = logging.getLogger(__name__)


def get_dkg_client(node_id, skale, sgx_key_name, rotation_id):
    dkg_client = None
    try:
        dkg_client = init_dkg_client(node_id, skale, sgx_key_name, rotation_id)
    except DkgError as e:
        logger.exception(e)
        raise
    if not dkg_client:
        raise DkgError('Dkg client was not inited successfully')
    return dkg_client


def init_bls(dkg_client):
    check_dkg_id_with_exception(dkg_client)

    if not broadcast_and_check_data(dkg_client):
        logger.exception('DKG broadcast data is not correct')
        while dkg_client.check_round_id():
            logger.info('Waiting for the next DKG round to start')
            sleep(BROADCAST_DATA_SEARCH_SLEEP)

    logger.info('All broadcasted data is correct - sending alright ...')
    send_alright_and_wait_for_others(dkg_client)

    logger.info('DKG completed successfully')


def is_last_dkg_finished(skale):
    return skale.dkg.get_round(skale.dkg.get_last_dkg_id()).status == Status.SUCCESS


def run_dkg(skale, dkg_client) -> DKGResult:
    keys_data, status = None, None
    try:
        if is_last_dkg_finished(skale):
            logger.info('Dkg is completed. Fetching data')
            dkg_client.fetch_all_broadcasted_data()
        else:
            logger.info('Starting DKG procedure')
            status = DKGStatus.IN_PROGRESS
            init_bls(dkg_client)
    except DkgError as e:
        logger.info(f'DKG procedure failed with {e}')
        status = DKGStatus.FAILED

    if not dkg_client:
        status = DKGStatus.FAILED

    if status != DKGStatus.FAILED:
        try:
            keys_data = generate_bls_keys(dkg_client)
        except DKGKeyGenerationError as e:
            logger.info(f'DKG failed during key generation, err {e}')
            status = DKGStatus.KEY_GENERATION_ERROR

    if keys_data:
        status = DKGStatus.DONE
    else:
        if status != DKGStatus.KEY_GENERATION_ERROR:
            status = DKGStatus.FAILED
    return DKGResult(keys_data=keys_data, step=dkg_client.last_completed_step, status=status)
