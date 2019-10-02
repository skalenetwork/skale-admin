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

import logging
from http import HTTPStatus

from flask import Blueprint, request, abort

from web.helper import construct_ok_response, construct_response, login_required, \
    construct_err_response

logger = logging.getLogger(__name__)


def construct_nodes_bp(skale, node, docker_utils):
    nodes_bp = Blueprint('nodes', __name__)

    @nodes_bp.route('/node-info', methods=['GET'])
    @login_required
    def node_info():
        logger.debug(request)
        node_info = node.get_node_info()
        return construct_ok_response(node_info)

    @nodes_bp.route('/create-node', methods=['POST'])
    @login_required
    def create_node():
        logger.debug(request)
        if not request.json:
            abort(400)

        ip = request.json.get('ip')
        public_ip = request.json.get('publicIP')
        port = request.json.get('port')
        name = request.json.get('name')

        is_node_name_available = skale.nodes_data.is_node_name_available(name)
        if not is_node_name_available:
            error_msg = f'Node name is already taken: {name}'
            logger.error(error_msg)
            return construct_err_response(HTTPStatus.BAD_REQUEST, [error_msg])

        is_node_ip_available = skale.nodes_data.is_node_ip_available(ip)
        if not is_node_ip_available:
            error_msg = f'Node IP is already taken: {ip}'
            logger.error(error_msg)
            return construct_err_response(HTTPStatus.BAD_REQUEST, [error_msg])

        res = node.create(ip, public_ip, port, name)
        if res['status'] != 1:
            return construct_err_response(HTTPStatus.INTERNAL_SERVER_ERROR, res['errors'])
        return construct_response(HTTPStatus.CREATED, res['data'])

    @nodes_bp.route('/uninstall-node', methods=['GET'])
    @login_required
    def uninstall_node():
        logger.debug(request)
        res = node.uninstall()
        return construct_ok_response(res)

    @nodes_bp.route('/check-node-name', methods=['GET'])
    @login_required
    def check_node_name():
        logger.debug(request)
        node_name = request.args.get('nodeName')
        res = skale.nodes_data.is_node_name_available(node_name)
        return construct_ok_response(res)

    @nodes_bp.route('/check-node-ip', methods=['GET'])
    @login_required
    def check_node_ip():
        logger.debug(request)
        node_ip = request.args.get('nodeIp')
        res = skale.nodes_data.is_node_ip_available(node_ip)
        return construct_ok_response(res)

    @nodes_bp.route('/containers/list', methods=['GET'])
    @login_required
    def skale_containers_list():
        logger.debug(request)
        all = request.args.get('all') == 'True'
        containers_list = docker_utils.get_all_skale_containers(all=all, format=True)
        return construct_ok_response(containers_list)

    return nodes_bp