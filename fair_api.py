#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

import binascii
import logging
import os
import time
from http import HTTPStatus

from flask import Flask, g
from werkzeug import exceptions as wz_exceptions

from core.node_config import NodeConfig
from tools.configs import FLASK_SECRET_KEY_FILE, PASSIVE_NODE
from tools.docker_utils import DockerUtils
from tools.helper import wait_until_admin_inited
from tools.logger import init_api_logger
from web.helper import construct_err_response
from web.routes.fair_chain import fair_chain_bp
from web.routes.fair_node import fair_node_bp
from web.routes.fair_node_passive import fair_node_passive_bp
from web.routes.fair_staking import fair_staking_bp
from web.routes.fair_wallet import wallet_bp
from web.routes.info import info_bp
from web.routes.ssl import ssl_bp

REQ_ID_SIZE = 10


init_api_logger()
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.register_blueprint(fair_chain_bp)
app.register_blueprint(ssl_bp)
app.register_blueprint(info_bp)

if PASSIVE_NODE:
    app.register_blueprint(fair_node_passive_bp)
else:
    app.register_blueprint(fair_node_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(fair_staking_bp)


@app.before_request
def before_request():
    wait_until_admin_inited()
    g.request_start_time = time.time()
    g.config = NodeConfig()
    g.request_id = binascii.b2a_hex(os.urandom(REQ_ID_SIZE // 2)).decode('utf-8')
    g.docker_utils = DockerUtils()
    logger.info(f'Processing request {g.request_id}')


@app.teardown_request
def teardown_request(response):
    elapsed = int(time.time() - g.request_start_time)
    logger.info(f'Request finished {g.request_id}, time elapsed: {elapsed}s')
    return response


@app.errorhandler(RecursionError)
def recursion_error_handler(e):
    return construct_err_response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        msg='Unexpected RecursionError in API, try again',
    )


@app.errorhandler(wz_exceptions.InternalServerError)
def any_error_handler(e):
    original = getattr(e, 'original_exception', None)
    logger.exception('Request failed with error %s', original)
    return construct_err_response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, msg=str(e))


app.secret_key = FLASK_SECRET_KEY_FILE
logger.info('Starting Fair API ...')
