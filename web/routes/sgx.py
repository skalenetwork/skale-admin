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
from enum import Enum

from flask import Blueprint, request
from sgx import SgxClient

from web.helper import construct_ok_response, login_required
from tools.sgx_utils import SGX_SERVER_URL
from tools.configs import SGX_CERTIFICATES_FOLDER

logger = logging.getLogger(__name__)
sgx_bp = Blueprint('sgx', __name__)


class SGXStatus(Enum):
    CONNECTED = 0
    NOT_CONNECTED = 1


@sgx_bp.route('/api/sgx/status', methods=['GET'])
@login_required
def sgx_status():
    logger.debug(request)
    sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
    try:
        status = sgx.get_server_status()
    except Exception:  # todo: catch specific error - edit sgx.py
        status = 1
    res = {
        'status': status,
        'status_name': SGXStatus(status).name,
        'sgx_server_url': SGX_SERVER_URL
    }
    return construct_ok_response(res)
