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

from web.helper import construct_ok_response
from tools.configs.flask import SKALE_LIB_NAME

from tools.configs.web3 import ENDPOINT

logger = logging.getLogger(__name__)


def construct_node_info_bp(skale, docker_utils):
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
        containers_list = docker_utils.get_all_skale_containers(all=all, format=True)
        return construct_ok_response(containers_list)

    @node_info_bp.route('/about-node', methods=['GET'])
    def about_node():
        logger.debug(request)

        node_about = {
            'libraries': {
                'javascript': 'N/A',  # get_js_package_version(),
                'skale.py': pkg_resources.get_distribution(SKALE_LIB_NAME).version
            },
            'contracts': {
                'token': skale.token.address,
                'manager': skale.manager.address,
            },
            'network': {
                'endpoint': ENDPOINT
            },
        }
        return construct_ok_response(node_about)

    return node_info_bp
