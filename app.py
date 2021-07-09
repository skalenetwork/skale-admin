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
import time

from flask import Flask, g


from core.node_config import NodeConfig

from tools.configs import FLASK_SECRET_KEY_FILE, SGX_SERVER_URL
from tools.configs.flask import (
    FLASK_APP_HOST,
    FLASK_APP_PORT,
    FLASK_DEBUG_MODE
)
from tools.configs.web3 import ENDPOINT
from tools.db import get_database, REDIS_URI
from tools.docker_utils import DockerUtils
from tools.helper import wait_until_admin_inited
from tools.wallet_utils import init_wallet
from tools.logger import init_api_logger
from tools.str_formatters import arguments_list_string

from web.routes.node import construct_node_bp
from web.routes.schains import construct_schains_bp
from web.routes.wallet import construct_wallet_bp
from web.routes.ssl import construct_ssl_bp
from web.routes.health import construct_health_bp

init_api_logger()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(construct_node_bp())
app.register_blueprint(construct_schains_bp())
app.register_blueprint(construct_wallet_bp())
app.register_blueprint(construct_ssl_bp())
app.register_blueprint(construct_health_bp())


@app.before_request
def before_request():
    wait_until_admin_inited()
    g.request_start_time = time.time()
    g.config = NodeConfig()
    g.wallet = init_wallet(node_config=g.config)
    g.db = get_database()
    g.db.connect(reuse_if_open=True)
    g.docker_utils = DockerUtils()


@app.teardown_request
def teardown_request(response):
    elapsed = int(time.time() - g.request_start_time)
    logger.info(f'Request time elapsed: {elapsed}s')
    if not g.db.is_closed():
        g.db.close()
    return response


app.secret_key = FLASK_SECRET_KEY_FILE
app.use_reloader = False
logger.info('Starting api ...')


def main():
    logger.info(arguments_list_string({
        'Endpoint': ENDPOINT,
        'Redis uri': REDIS_URI,
        'SGX Server': SGX_SERVER_URL or 'Not connected'
        }, 'Starting Flask server'))
    app.run(debug=FLASK_DEBUG_MODE, port=FLASK_APP_PORT, host=FLASK_APP_HOST)


if __name__ == '__main__':
    main()
