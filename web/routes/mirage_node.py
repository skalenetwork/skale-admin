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

import logging
from http import HTTPStatus

from flask import Blueprint, abort, g, request
from skale import MirageManager
from skale.transactions.exceptions import TransactionError

from core.node_config import NodeConfig
from web.helper import construct_err_response, construct_ok_response, g_mirage, get_api_url

logger = logging.getLogger(__name__)

BLUEPRINT_NAME = 'mirage-node'
mirage_node_bp = Blueprint(BLUEPRINT_NAME, __name__)


@mirage_node_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
@g_mirage
def info():
    logger.debug(request)
    node_config: NodeConfig = g.config
    mirage: MirageManager = g.mirage
    if not node_config.id:
        return construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )
    node = mirage.nodes.get(node_config.id)
    return construct_ok_response({'node': node.to_dict()})


@mirage_node_bp.route(get_api_url(BLUEPRINT_NAME, 'register'), methods=['POST'])
@g_mirage
def register():
    logger.debug(request)
    if not request.json:
        abort(400)

    ip = request.json.get('ip')
    port = request.json.get('port')

    mirage: MirageManager = g.mirage
    try:
        mirage.nodes.register_active(ip, port)
    except TransactionError as e:
        logger.error(f'Error registering node: {e}')
        return construct_err_response(
            msg=f'Error registering node: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    node_config: NodeConfig = NodeConfig()
    node = mirage.nodes.get_by_address(mirage.wallet.address)
    node_config.id = node.id
    node_config.ip = ip
    node_config.schain_base_port = port
    return construct_ok_response({'node': node.to_dict()})


@mirage_node_bp.route(get_api_url(BLUEPRINT_NAME, 'set-domain-name'), methods=['POST'])
@g_mirage
def set_domain_name():
    logger.debug(request)
    if not request.json or 'domain_name' not in request.json:
        return construct_err_response(
            msg='Domain name is required', status_code=HTTPStatus.BAD_REQUEST
        )

    domain_name = request.json['domain_name']

    mirage: MirageManager = g.mirage
    node_config: NodeConfig = g.config

    if not node_config.id:
        return construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )

    try:
        mirage.nodes.set_domain_name(node_config.id, domain_name)
    except TransactionError as e:
        logger.error(f'Error setting domain name: {e}')
        return construct_err_response(
            msg=f'Error setting domain name: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()
