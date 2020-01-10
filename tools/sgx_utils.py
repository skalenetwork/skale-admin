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

import os
import logging

from sgx import SgxClient
from tools.configs import SGX_CERTIFICATES_FOLDER
from tools.str_formatters import arguments_list_string


logger = logging.getLogger(__name__)

SGX_KEY_CONFIG_NAME = 'sgx_key_name'
SGX_SERVER_URL = os.environ.get('SGX_SERVER_URL')


class SGXConnecionError(Exception):
    """Raised when admin couldn't establish connection with SGX server"""


def generate_sgx_key(config):
    if not SGX_SERVER_URL:
        raise SGXConnecionError('SGX server URL is not provided')
    if not config.sgx_key_name:
        sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
        key_info = sgx.generate_key()
        logger.info(arguments_list_string({
            'Name': key_info.name,
            'Address': key_info.address
            }, 'Generated new SGX key'))
        config.sgx_key_name = key_info.name


def sgx_server_text():
    if SGX_SERVER_URL:
        return SGX_SERVER_URL
    return 'Not connected'
