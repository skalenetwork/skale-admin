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

from core.node import Node
from tools.helper import init_skale

from core.node import get_meta_info, get_node_hardware_info
from tools.configs.web3 import ENDPOINT, UNTRUSTED_PROVIDERS
from tools.custom_thread import CustomThread
from tools.notifications.messages import send_message, tg_notifications_enabled
from web.helper import construct_err_response, construct_ok_response, get_api_url

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'node'


def construct_node_bp():
    node_bp = Blueprint(BLUEPRINT_NAME, __name__)

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
    def info():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        data = {'node_info': node.info}
        return construct_ok_response(data=data)

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'register'), methods=['POST'])
    def register():
        logger.debug(request)
        if not request.json:
            abort(400)

        skale = init_skale(g.wallet)

        ip = request.json.get('ip')
        public_ip = request.json.get('public_ip', None)
        port = request.json.get('port')
        name = request.json.get('name')
        domain_name = request.json.get('domain_name')
        gas_price = request.json.get('gas_price')
        gas_limit = request.json.get('gas_limit')
        skip_dry_run = request.json.get('skip_dry_run')

        if not public_ip:
            public_ip = ip

        if gas_price is not None:
            gas_price = Web3.toWei(Decimal(gas_price), 'gwei')

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
        if res['status'] != 'ok':
            return construct_err_response(
                msg=res['errors'],
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR
            )
        return construct_ok_response({'node_data': res['data']})

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'signature'), methods=['GET'])
    def signature():
        logger.debug(request)
        validator_id = int(request.args.get('validator_id'))
        skale = init_skale(g.wallet)
        signature = skale.validator_service.get_link_node_signature(
            validator_id)
        return construct_ok_response(data={'signature': signature})

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'maintenance-on'), methods=['POST'])
    def set_node_maintenance_on():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_maintenance_on()
        if res['status'] != 'ok':
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'maintenance-off'), methods=['POST'])
    def set_node_maintenance_off():
        logger.debug(request)
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_maintenance_off()
        if res['status'] != 'ok':
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'send-tg-notification'), methods=['POST'])
    def send_tg_notification():
        logger.debug(request)
        message = request.json.get('message')
        if not message:
            return construct_err_response('Message is empty')
        if not tg_notifications_enabled():
            return construct_err_response('TG_API_KEY or TG_CHAT_ID not found')
        try:
            send_message(message)
        except Exception:
            logger.exception('Message was not send due to error')
            construct_err_response(['Message sending failed'])
        return construct_ok_response('Message was sent successfully')

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'exit/start'), methods=['POST'])
    def exit_start():
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        exit_thread = CustomThread('Start node exit', node.exit, once=True)
        exit_thread.start()
        return construct_ok_response()

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'exit/status'), methods=['GET'])
    def exit_status():
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        exit_status_data = node.get_exit_status()
        return construct_ok_response(exit_status_data)

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'set-domain-name'), methods=['POST'])
    def set_domain_name():
        logger.debug(request)
        domain_name = request.json['domain_name']
        skale = init_skale(g.wallet)
        node = Node(skale, g.config)
        res = node.set_domain_name(domain_name)
        if res['status'] != 'ok':
            return construct_err_response(msg=res['errors'])
        return construct_ok_response()

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'hardware'), methods=['GET'])
    def hardware():
        logger.debug(request)
        hardware_info = get_node_hardware_info()
        return construct_ok_response(hardware_info)

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'endpoint-info'), methods=['GET'])
    def endpoint_info():
        logger.debug(request)
        skale = init_skale(wallet=g.wallet)
        block_number = skale.web3.eth.blockNumber
        syncing = skale.web3.eth.syncing
        trusted = not any([untrusted in ENDPOINT for untrusted in UNTRUSTED_PROVIDERS])
        try:
            eth_client_version = skale.web3.clientVersion
        except Exception:
            logger.exception('Cannot get client version')
            eth_client_version = 'unknown'
        geth_client = 'Geth' in eth_client_version
        info = {
            'block_number': block_number,
            'syncing': syncing,
            'trusted': trusted and geth_client,
            'client': eth_client_version
        }
        return construct_ok_response(info)

    @node_bp.route(get_api_url(BLUEPRINT_NAME, 'meta-info'), methods=['GET'])
    def meta_info():
        logger.debug(request)
        version_data = get_meta_info()
        return construct_ok_response(version_data)

    return node_bp
