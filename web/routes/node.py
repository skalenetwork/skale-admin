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

from flask import Blueprint, abort, g, request

from core.node import Node, NodeStatus

from tools.custom_thread import CustomThread
from tools.notifications.messages import send_message, tg_notifications_enabled
from web.helper import construct_err_response, construct_ok_response, get_api_url, g_skale

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'node'


IPIFY_URL = 'https://api.ipify.org?format=json'
GET_IP_ATTEMPTS = 5


node_bp = Blueprint(BLUEPRINT_NAME, __name__)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'info'), methods=['GET'])
@g_skale
def info():
    logger.debug(request)
    node = Node(g.skale, g.config)
    data = {'node_info': node.info}
    return construct_ok_response(data=data)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'register'), methods=['POST'])
@g_skale
def register():
    logger.debug(request)
    if not request.json:
        abort(400)

    ip = request.json.get('ip')
    public_ip = request.json.get('public_ip', None)
    port = request.json.get('port')
    name = request.json.get('name')
    domain_name = request.json.get('domain_name')

    if not public_ip:
        public_ip = ip

    node = Node(g.skale, g.config)
    res = node.register(ip=ip, public_ip=public_ip, port=port, name=name, domain_name=domain_name)
    if res['status'] != 'ok':
        return construct_err_response(
            msg=res['errors'], status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response({'node_data': res['data']})


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'signature'), methods=['GET'])
@g_skale
def signature():
    logger.debug(request)
    validator_id = int(request.args.get('validator_id'))
    signature = g.skale.validator_service.get_link_node_signature(validator_id)
    return construct_ok_response(data={'signature': signature})


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'maintenance-on'), methods=['POST'])
@g_skale
def set_node_maintenance_on():
    logger.debug(request)
    node = Node(g.skale, g.config)
    res = node.set_maintenance_on()
    if res['status'] != 'ok':
        return construct_err_response(msg=res['errors'])
    return construct_ok_response()


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'maintenance-off'), methods=['POST'])
@g_skale
def set_node_maintenance_off():
    logger.debug(request)
    node = Node(g.skale, g.config)
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
@g_skale
def exit_start():
    node = Node(g.skale, g.config)
    if g.skale.nodes.get_node_status(g.config.id) == NodeStatus.IN_MAINTENANCE.value:
        return construct_err_response(msg='Node is in maintenance')
    exit_thread = CustomThread('Start node exit', node.exit, once=True)
    exit_thread.start()
    return construct_ok_response()


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'exit/status'), methods=['GET'])
@g_skale
def exit_status():
    node = Node(g.skale, g.config)
    exit_status_data = node.get_exit_status()
    return construct_ok_response(exit_status_data)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'set-domain-name'), methods=['POST'])
@g_skale
def set_domain_name():
    logger.debug(request)
    domain_name = request.json['domain_name']

    node = Node(g.skale, g.config)
    res = node.set_domain_name(domain_name)
    if res['status'] != 'ok':
        return construct_err_response(msg=res['errors'])
    return construct_ok_response()
