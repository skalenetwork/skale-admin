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
from skale import FairManager

from core.node_config import NodeConfig
from web.helper import (
    construct_err_response,
    construct_ok_response,
    g_fair_passive,
    get_api_url,
)

logger = logging.getLogger(__name__)

BLUEPRINT_NAME = 'fair-node-passive'
fair_node_passive_bp = Blueprint(BLUEPRINT_NAME, __name__)


@fair_node_passive_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
@g_fair_passive
def info():
    logger.debug(request)
    node_config: NodeConfig = g.config
    fair: FairManager = g.fair
    if not node_config.id:
        return construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )
    node = fair.nodes.get(node_config.id)
    return construct_ok_response({'node': node.to_dict()})


@fair_node_passive_bp.route(get_api_url(BLUEPRINT_NAME, 'setup'), methods=['POST'])
@g_fair_passive
def setup():
    logger.debug(request)
    if not request.json:
        abort(400)

    id = request.json.get('id')
    fair: FairManager = g.fair

    node_config: NodeConfig = NodeConfig()
    node = fair.nodes.get(id)
    node_config.id = node.id
    node_config.ip = node.ip_str
    node_config.schain_base_port = node.port
    return construct_ok_response({'node': node.to_dict()})
