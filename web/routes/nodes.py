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
from decimal import Decimal
from http import HTTPStatus

from flask import Blueprint, abort, g, request
from web3 import Web3

from core.node import Node, check_validator_nodes
from tools.helper import init_skale
from web.helper import construct_ok_response, construct_err_response


logger = logging.getLogger(__name__)


def construct_nodes_bp():
    nodes_bp = Blueprint('nodes', __name__)

    @nodes_bp.route('/node-info', methods=['GET'])
    def node_info():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        data = {'node_info': node.info}
        return construct_ok_response(data=data)

    @nodes_bp.route('/create-node', methods=['POST'])
    def register_node():
        logger.debug(request)
        if not request.json:
            abort(400)

        skale = init_skale(g.wallet)

        ip = request.json.get('ip')
        public_ip = request.json.get('publicIP')
        port = request.json.get('port')
        name = request.json.get('name')
        domain_name = request.json.get('domain_name')
        gas_price = request.json.get('gas_price')
        gas_limit = request.json.get('gas_limit')
        skip_dry_run = request.json.get('skip_dry_run')

        if gas_price is not None:
            gas_price = Web3.toWei(Decimal(gas_price), 'gwei')

        is_node_name_available = skale.nodes.is_node_name_available(name)
        if not is_node_name_available:
            error_msg = f'Node name is already taken: {name}'
            logger.error(error_msg)
            return construct_err_response(msg=error_msg)

        is_node_ip_available = skale.nodes.is_node_ip_available(ip)
        if not is_node_ip_available:
            error_msg = f'Node IP is already taken: {ip}'
            logger.error(error_msg)
            return construct_err_response(error_msg)

        node = Node(skale, g.config)
        res = node.register(
            ip=ip,
            public_ip=public_ip,
            port=port,
            name=name,
            domain_name=domain_name,
            gas_price=gas_price,
            gas_limit=gas_limit,
            skip_dry_run=skip_dry_run
        )
        if res['status'] != 1:
            return construct_err_response(
                msg=res['errors'],
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR
            )
        return construct_ok_response({'node_data': res['data']})

    @nodes_bp.route('/node-signature', methods=['GET'])
    def node_signature():
        logger.debug(request)

        validator_id = int(request.args.get('validator_id'))
        skale = init_skale(g.wallet)

        signature = skale.validator_service.get_link_node_signature(
            validator_id)
        return construct_ok_response(data={'signature': signature})

    @nodes_bp.route('/check-node-name', methods=['GET'])
    def check_node_name():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node_name = request.args.get('nodeName')
        res = skale.nodes.is_node_name_available(node_name)
        return construct_ok_response(data={'name_available': res})

    @nodes_bp.route('/check-node-ip', methods=['GET'])
    def check_node_ip():
        skale = init_skale(g.wallet)
        logger.debug(request)
        node_ip = request.args.get('nodeIp')
        res = skale.nodes.is_node_ip_available(node_ip)
        return construct_ok_response(data={'ip_available': res})

    @nodes_bp.route('/containers/list', methods=['GET'])
    def skale_containers_list():
        logger.debug(request)
        all = request.args.get('all') == 'True'
        containers_list = g.docker_utils.get_all_skale_containers(
            all=all, format=True)
        return construct_ok_response(data={'containers': containers_list})

    @nodes_bp.route('/api/node/maintenance-on', methods=['POST'])
    def set_node_maintenance_on():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_maintenance_on()
        if res['status'] != 0:
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @nodes_bp.route('/api/node/maintenance-off', methods=['POST'])
    def set_node_maintenance_off():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_maintenance_off()
        if res['status'] != 0:
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @nodes_bp.route('/api/node/set-domain-name', methods=['POST'])
    def set_domain_name():
        logger.debug(request)
        domain_name = request.json['domain_name']
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_domain_name(domain_name)
        if res['status'] != 0:
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @nodes_bp.route('/api/v1/health/validator-nodes', methods=['GET'])
    def _validator_nodes():
        logger.debug(request)
        skale = init_skale(g.wallet)
        res = check_validator_nodes(skale, g.config.id)
        if res['status'] != 0:
            return construct_err_response(msg=res['errors'])
        return construct_ok_response(data=res['data'])

    return nodes_bp
