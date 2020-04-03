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

from skale.schain_config.generator import get_nodes_for_schain_config
from core.schains.helper import get_schain_config
from web.models.schain import SChainRecord
from web.helper import construct_ok_response, construct_err_response, construct_key_error_response

logger = logging.getLogger(__name__)


def construct_schains_bp(skale, config, docker_utils):
    schains_bp = Blueprint('schains', __name__)

    @schains_bp.route('/get-owner-schains', methods=['GET'])
    def owner_schains():
        logger.debug(request)
        schains = skale.schains_data.get_schains_for_owner(skale.wallet.address)
        for schain in schains:
            nodes = get_nodes_for_schain_config(skale, schain['name'])
            schain['nodes'] = nodes
        return construct_ok_response(schains)

    @schains_bp.route('/schain-config', methods=['GET'])
    def get_schain_config_route():
        logger.debug(request)
        key = 'schain-name'
        schain_name = request.args.get(key)
        if not schain_name:
            return construct_key_error_response([key])
        try:
            schain_config = get_schain_config(schain_name)
        except FileNotFoundError:
            return construct_err_response(
                HTTPStatus.BAD_REQUEST, 
                [f'sChain config not found: {schain_name}']
            )
        skale_schain_config = schain_config['skaleConfig']
        return construct_ok_response(skale_schain_config)

    @schains_bp.route('/containers/schains/list', methods=['GET'])
    def schains_containers_list():
        logger.debug(request)
        _all = request.args.get('all') == 'True'
        containers_list = docker_utils.get_all_schain_containers(all=_all, format=True)
        return construct_ok_response(containers_list)

    @schains_bp.route('/schains/list', methods=['GET'])
    def node_schains_list():
        logger.debug(request)
        node_id = config.id
        if node_id is None:
            return construct_err_response(HTTPStatus.BAD_REQUEST, ['No node installed'])
        schains_list = skale.schains_data.get_schains_for_node(node_id)
        return construct_ok_response(schains_list)

    @schains_bp.route('/api/dkg/statuses', methods=['GET'])
    def dkg_status():
        logger.debug(request)
        _all = request.args.get('all') == 'True'
        dkg_statuses = SChainRecord.get_statuses(_all)
        return construct_ok_response(dkg_statuses)

    return schains_bp
