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
import json
from http import HTTPStatus

from flask import Response
from skale import Skale

from core.node_config import NodeConfig
from tools.helper import init_skale
from tools.wallet_utils import init_wallet
from web import API_VERSION_PREFIX


logger = logging.getLogger(__name__)


def construct_response(status, data):
    return Response(
        response=json.dumps(data),
        status=status,
        mimetype='application/json'
    )


def construct_ok_response(data=None):
    if data is None:
        data = {}
    return construct_response(HTTPStatus.OK, {'status': 'ok', 'payload': data})


def construct_err_response(msg=None, status_code=HTTPStatus.BAD_REQUEST):
    if msg is None:
        msg = {}
    return construct_response(status_code, {'status': 'error', 'payload': msg})


def construct_key_error_response(absent_keys):
    keys_str = ', '.join(absent_keys)
    msg = f'Required arguments: {keys_str}'
    return construct_err_response(msg=msg)


def get_api_url(blueprint_name, method_name):
    return os.path.join(API_VERSION_PREFIX, blueprint_name, method_name)


def init_skale_from_node_config(node_config: NodeConfig) -> Skale:
    wallet = init_wallet(node_config)
    return init_skale(wallet)
