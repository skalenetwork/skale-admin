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
from http import HTTPStatus

from flask import Blueprint, request

from core.schains.helper import get_schain_config
from web.helper import construct_ok_response, construct_err_response, login_required

logger = logging.getLogger(__name__)


def construct_schains_bp(skale, config, docker_utils):
    schains_bp = Blueprint('schains', __name__)

    @schains_bp.route('/get-owner-schains', methods=['GET'])
    @login_required
    def owner_schains():
        logger.debug(request)
        schains = skale.schains_data.get_schains_for_owner(skale.wallet.address)
        for schain in schains:
            nodes = skale.schains_data.get_nodes_for_schain_config(schain['name'])
            schain['nodes'] = nodes
        return construct_ok_response(schains)

    @schains_bp.route('/schain-config', methods=['GET'])
    @login_required
    def get_schain_config_route():
        logger.debug(request)
        schain_name = request.args.get('schain-name')
        # todo: handle - if schain name is empty or invalid
        schain_config = get_schain_config(schain_name)
        skale_schain_config = schain_config['skaleConfig']
        return construct_ok_response(skale_schain_config)

    @schains_bp.route('/containers/schains/list', methods=['GET'])
    @login_required
    def schains_containers_list():
        logger.debug(request)
        _all = request.args.get('all') == 'True'
        containers_list = docker_utils.get_all_schain_containers(all=_all, format=True)
        return construct_ok_response(containers_list)

    @schains_bp.route('/schains/list', methods=['GET'])
    @login_required
    def node_schains_list():
        logger.debug(request)
        node_id = config.id
        if node_id is None:
            return construct_err_response(HTTPStatus.BAD_REQUEST, ['No node installed'])
        schains_list = skale.schains_data.get_schains_for_node(node_id)
        return construct_ok_response(schains_list)

    return schains_bp
