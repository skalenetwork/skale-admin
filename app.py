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

from flask import Flask, render_template, session, g
from peewee import SqliteDatabase

from skale import Skale
from skale.wallets import RPCWallet

from core.node import Node
from core.node_config import NodeConfig
from core.schains.monitor import SchainsMonitor
from core.schains.cleaner import SChainsCleaner

from tools.configs import FLASK_SECRET_KEY_FILE
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, TM_URL
from tools.configs.db import DB_FILE
from tools.logger import init_admin_logger
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from tools.sgx_utils import generate_sgx_key, sgx_server_text
from tools.token_utils import init_user_token

from tools.configs.flask import FLASK_APP_HOST, FLASK_APP_PORT, FLASK_DEBUG_MODE
from web.models.user import User
from web.models.schain import SChainRecord
from web.user_session import UserSession

from web.routes.auth import construct_auth_bp
from web.routes.logs import web_logs
from web.routes.nodes import construct_nodes_bp
from web.routes.schains import construct_schains_bp
from web.routes.wallet import construct_wallet_bp
from web.routes.node_info import construct_node_info_bp
from web.routes.security import construct_security_bp
from web.routes.validators import construct_validators_bp
from web.routes.metrics import construct_metrics_bp
from web.routes.node_exit import construct_node_exit_bp
from web.routes.sgx import sgx_bp

init_admin_logger()
logger = logging.getLogger(__name__)
werkzeug_logger = logging.getLogger('werkzeug')  # todo: remove
werkzeug_logger.setLevel(logging.WARNING)  # todo: remove

rpc_wallet = RPCWallet(TM_URL)
skale = Skale(ENDPOINT, ABI_FILEPATH, rpc_wallet)

docker_utils = DockerUtils()
user_session = UserSession(session)

node_config = NodeConfig()
node = Node(skale, node_config)
schains_monitor = SchainsMonitor(skale, node_config)
schains_cleaner = SChainsCleaner(skale, node_config)

token = init_user_token()
database = SqliteDatabase(DB_FILE)

app = Flask(__name__)
app.register_blueprint(construct_auth_bp(user_session, token))
app.register_blueprint(web_logs)
app.register_blueprint(construct_nodes_bp(skale, node, docker_utils))
app.register_blueprint(construct_schains_bp(skale, node_config, docker_utils))
app.register_blueprint(construct_wallet_bp(skale))
app.register_blueprint(construct_node_info_bp(skale, docker_utils))
app.register_blueprint(construct_security_bp())
app.register_blueprint(construct_validators_bp(skale, node_config))
app.register_blueprint(construct_metrics_bp(skale, node_config))
app.register_blueprint(construct_node_exit_bp(skale))
app.register_blueprint(sgx_bp)


@app.before_request
def before_request():
    g.db = database
    g.db.connect()


@app.after_request
def after_request(response):
    g.db.close()
    return response


def create_tables():
    if not User.table_exists():
        User.create_table()
    if not SChainRecord.table_exists():
        SChainRecord.create_table()


if __name__ == '__main__':
    logger.info(arguments_list_string({
        'Endpoint': ENDPOINT,
        'Transaction manager': TM_URL,
        'SGX Server': sgx_server_text()
        }, 'Starting Flask server'))
    create_tables()
    generate_sgx_key(node_config)
    app.secret_key = FLASK_SECRET_KEY_FILE
    app.run(debug=FLASK_DEBUG_MODE, port=FLASK_APP_PORT, host=FLASK_APP_HOST, use_reloader=False)
