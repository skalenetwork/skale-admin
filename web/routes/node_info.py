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
import pkg_resources

from flask import Blueprint, request

from web.helper import construct_ok_response, login_required
from tools.configs.flask import SKALE_LIB_NAME

from tools.configs.web3 import ENDPOINT

logger = logging.getLogger(__name__)


def construct_node_info_bp(skale, wallet, docker_utils):
    node_info_bp = Blueprint('node_info', __name__)

    @node_info_bp.route('/get-rpc-credentials', methods=['GET'])
    def get_rpc_credentials():
        logger.debug(request)
        rpc_credentials = {
            'endpoint': ENDPOINT
        }
        return construct_ok_response(rpc_credentials)

    # todo: add option to disable all unauthorized requests
    @node_info_bp.route('/healthchecks/containers', methods=['GET'])
    def containers_healthcheck():
        logger.debug(request)
        base_containers_list = docker_utils.get_base_skale_containers(
            all=True, format=True)
        return construct_ok_response(base_containers_list)

    @node_info_bp.route('/about-node', methods=['GET'])
    @login_required
    def about_node():
        logger.debug(request)

        node_about = {
            'libraries': {
                'javascript': 'N/A',  # get_js_package_version(),
                'python': pkg_resources.get_distribution(SKALE_LIB_NAME).version
            },
            'contracts': {
                'token': skale.token.address,
                'manager': skale.manager.address,
            },
            'network': {
                'endpoint': ENDPOINT
            },
            'local_wallet': wallet.get_with_balance()
        }
        return construct_ok_response(node_about)

    return node_info_bp
