#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import logging

from flask import Flask, render_template, session, g
from peewee import SqliteDatabase

import sentry_sdk

from skale import Skale

from core.node import Node
from core.local_wallet import LocalWallet

from tools.helper import get_sentry_env_name
from tools.config import NODE_CONFIG_FILEPATH, DB_FILE, FLASK_SECRET_KEY_FILE, CONTAINERS_FILEPATH
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH
from tools.logger import init_admin_logger
from tools.config_storage import ConfigStorage
from tools.token_utils import TokenUtils
from tools.dockertools import DockerManager
from tools.docker_utils import DockerUtils

from tools.configs.flask import FLASK_APP_HOST, FLASK_APP_PORT
from web.user import User
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

init_admin_logger()
logger = logging.getLogger(__name__)
werkzeug_logger = logging.getLogger('werkzeug')  # todo: remove
werkzeug_logger.setLevel(logging.WARNING)  # todo: remove

skale = Skale(ENDPOINT, ABI_FILEPATH)
wallet = LocalWallet(skale)
config = ConfigStorage(NODE_CONFIG_FILEPATH)
docker_manager = DockerManager(CONTAINERS_FILEPATH)
docker_utils = DockerUtils()
node = Node(skale, config, wallet, docker_manager)
token_utils = TokenUtils()
user_session = UserSession(session)

SENTRY_URL = os.environ.get('SENTRY_URL', None)
if SENTRY_URL:
    sentry_env_name = get_sentry_env_name(skale.manager.address)
    sentry_sdk.init(SENTRY_URL, environment=sentry_env_name)


if not token_utils.get_token():
    token_utils.add_token()
token = token_utils.get_token()

database = SqliteDatabase(DB_FILE)

app = Flask(__name__)
app.register_blueprint(construct_auth_bp(user_session, token))
app.register_blueprint(web_logs)
app.register_blueprint(construct_nodes_bp(skale, node, docker_utils))
app.register_blueprint(construct_schains_bp(skale, wallet, docker_utils, node))
app.register_blueprint(construct_wallet_bp(wallet))
app.register_blueprint(construct_node_info_bp(skale, wallet))
app.register_blueprint(construct_security_bp())
app.register_blueprint(construct_validators_bp(skale, config, wallet))
app.register_blueprint(construct_metrics_bp(skale, config, wallet))

wallet.get_or_generate()

@app.before_request
def before_request():
    g.db = database
    g.db.connect()


@app.after_request
def after_request(response):
    g.db.close()
    return response


@app.route('/')
def main():
    return render_template('index.html')


if __name__ == '__main__':
    logger.info('Starting Flask server')
    logger.info('=========================================')
    logger.info(f'Root account token: {token}')
    logger.info('=========================================')

    if not User.table_exists():
        User.create_table()

    app.secret_key = FLASK_SECRET_KEY_FILE
    app.run(debug=True, port=FLASK_APP_PORT, host=FLASK_APP_HOST, use_reloader=False)
