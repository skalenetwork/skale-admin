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

from flask import Flask, g

from skale import Skale
from skale.wallets import RPCWallet

from core.node import Node
from core.node_config import NodeConfig

from tools.configs import FLASK_SECRET_KEY_FILE
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, TM_URL
from tools.db import get_database
from tools.docker_utils import DockerUtils
from tools.logger import init_api_logger
from tools.sgx_utils import generate_sgx_key, sgx_server_text
from tools.str_formatters import arguments_list_string

from tools.configs.flask import FLASK_APP_HOST, FLASK_APP_PORT, FLASK_DEBUG_MODE

from web.models.schain import create_tables
from web.routes.logs import web_logs
from web.routes.node import construct_node_bp
from web.routes.schains import construct_schains_bp
from web.routes.wallet import construct_wallet_bp
from web.routes.security import construct_security_bp
from web.routes.node_exit import construct_node_exit_bp
from web.routes.sgx import construct_sgx_bp
from web.routes.health import construct_health_bp

init_api_logger()
logger = logging.getLogger(__name__)

rpc_wallet = RPCWallet(TM_URL)
skale = Skale(ENDPOINT, ABI_FILEPATH, rpc_wallet)
logger.info('Skale inited')

docker_utils = DockerUtils()
logger.info('Docker utils inited')

node_config = NodeConfig()
node = Node(skale, node_config)
logger.info('Node inited')

app = Flask(__name__)
app.register_blueprint(web_logs)
app.register_blueprint(construct_node_bp(skale, node, docker_utils))
app.register_blueprint(construct_schains_bp(skale, node_config, docker_utils))
app.register_blueprint(construct_wallet_bp(skale))
app.register_blueprint(construct_security_bp(docker_utils))
app.register_blueprint(construct_node_exit_bp(node))
app.register_blueprint(construct_sgx_bp(node_config))
app.register_blueprint(construct_health_bp(node_config, skale, docker_utils))


@app.before_request
def before_request():
    g.db = get_database()
    g.db.connect(reuse_if_open=True)


@app.teardown_request
def teardown_request(response):
    if not g.db.is_closed():
        g.db.close()
    return response


create_tables()
generate_sgx_key(node_config)
app.secret_key = FLASK_SECRET_KEY_FILE
app.use_reloader = False
logger.info('Starting api')


def main():
    logger.info(arguments_list_string({
        'Endpoint': ENDPOINT,
        'Transaction manager': TM_URL,
        'SGX Server': sgx_server_text()
        }, 'Starting Flask server'))
    app.run(debug=FLASK_DEBUG_MODE, port=FLASK_APP_PORT, host=FLASK_APP_HOST)


if __name__ == '__main__':
    main()
