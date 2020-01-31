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
import json
from http import HTTPStatus
from flask import Response


logger = logging.getLogger(__name__)


def construct_response(status, data):
    return Response(
        response=json.dumps(data),
        status=status,
        mimetype='application/json'
    )


def construct_bad_req_response(error_msg):
    return construct_response(HTTPStatus.BAD_REQUEST, {'res': 0, 'error_msg': error_msg})


def construct_err_response(status, errors=[]):
    logger.warning(f'error response: {errors}, status: {status}')
    return construct_response(status, {'errors': errors})


def construct_key_error_response(keys):
    keys_str = ', '.join(keys)
    err = f'Required arguments: {keys_str}'
    return construct_err_response(400, [err])


def construct_ok_response(data=None):
    return construct_response(HTTPStatus.OK, {'res': 1, 'data': data})
