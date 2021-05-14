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

import functools
import logging
import time

from sgx import SgxClient
from sgx.http import SgxUnreachableError
from tools.configs import SGX_CERTIFICATES_FOLDER, SGX_SERVER_URL
from tools.str_formatters import arguments_list_string


logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 14
TIMEOUTS = [2 ** p for p in range(RETRY_ATTEMPTS)]


class EmptySgxUrlError(Exception):
    """Raised when admin couldn't establish connection with SGX server"""


def sgx_unreachable_retry(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result, error = None, None
        for i, timeout in enumerate(TIMEOUTS):
            try:
                result = func(*args, **kwargs)
            except SgxUnreachableError as err:
                logger.info(f'Sgx server is unreachable during try {i}')
                error = err
                time.sleep(timeout)
            else:
                error = None
                break
        if error is not None:
            raise error
        return result
    return wrapper


@sgx_unreachable_retry
def generate_sgx_key(config):
    logger.info('Generating sgx key...')
    if not SGX_SERVER_URL:
        raise EmptySgxUrlError('SGX server URL is not provided')
    if not config.sgx_key_name:
        sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
        key_info = sgx.generate_key()
        logger.info(arguments_list_string({
            'Name hash': key_info.name,
            'Address': key_info.address
            }, 'Generated new SGX key'))
        config.sgx_key_name = key_info.name
