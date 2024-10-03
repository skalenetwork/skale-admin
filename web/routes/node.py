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

import time
import logging
from http import HTTPStatus

import requests
from flask import Blueprint, abort, g, request

from core.node import Node, NodeStatus
from tools.helper import get_endpoint_call_speed

from core.node import get_meta_info, get_node_hardware_info, get_btrfs_info, get_abi_hash
from core.node import check_validator_nodes
from core.updates import is_update_possible


from tools.configs.web3 import ABI_FILEPATH, ENDPOINT, UNTRUSTED_PROVIDERS
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH
from tools.custom_thread import CustomThread
from tools.notifications.messages import send_message, tg_notifications_enabled
from web.helper import (
    construct_err_response,
    construct_ok_response,
    get_api_url,
    g_skale,
    g_web3
)

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
    res = node.register(
        ip=ip,
        public_ip=public_ip,
        port=port,
        name=name,
        domain_name=domain_name
    )
    if res['status'] != 'ok':
        return construct_err_response(
            msg=res['errors'],
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response({'node_data': res['data']})


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'signature'), methods=['GET'])
@g_skale
def signature():
    logger.debug(request)
    validator_id = int(request.args.get('validator_id'))
    signature = g.skale.validator_service.get_link_node_signature(
        validator_id)
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


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'hardware'), methods=['GET'])
def hardware():
    logger.debug(request)
    hardware_info = get_node_hardware_info()
    return construct_ok_response(hardware_info)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'endpoint-info'), methods=['GET'])
@g_web3
def endpoint_info():
    logger.debug(request)
    call_speed = get_endpoint_call_speed(g.web3)
    block_number = g.web3.eth.block_number
    trusted = not any([untrusted in ENDPOINT for untrusted in UNTRUSTED_PROVIDERS])
    try:
        eth_client_version = g.web3.client_version
    except Exception:
        logger.exception('Cannot get client version')
        eth_client_version = 'unknown'
    geth_client = 'Geth' in eth_client_version
    syncing = False
    try:
        syncing = g.web3.eth.syncing
        if syncing is not False:
            syncing = True
    except Exception:
        logger.exception('eth_syncing request errored')
        syncing = None
    info = {
        'block_number': block_number,
        'trusted': trusted and geth_client,
        'client': eth_client_version,
        'call_speed': call_speed,
        'syncing': syncing
    }
    logger.info(f'endpoint info: {info}')
    return construct_ok_response(info)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'meta-info'), methods=['GET'])
def meta_info():
    logger.debug(request)
    version_data = get_meta_info()
    return construct_ok_response(version_data)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'btrfs-info'), methods=['GET'])
def btrfs_info():
    logger.debug(request)
    btrfs_data = get_btrfs_info()
    return construct_ok_response(btrfs_data)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'public-ip'), methods=['GET'])
def public_ip():
    logger.debug(request)
    for _ in range(GET_IP_ATTEMPTS):
        try:
            response = requests.get(IPIFY_URL)
            ip = response.json()['ip']
            return construct_ok_response({'public_ip': ip})
        except Exception:
            logger.exception('Ip request failed')
            time.sleep(1)
    return construct_err_response(msg='Public ip request failed')


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'validator-nodes'), methods=['GET'])
@g_skale
def _validator_nodes():
    logger.debug(request)
    if g.config.id is None:
        return construct_ok_response(data=[])
    res = check_validator_nodes(g.skale, g.config.id)
    if res['status'] != 0:
        return construct_err_response(msg=res['errors'])
    return construct_ok_response(data=res['data'])


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'sm-abi'), methods=['GET'])
def sm_abi():
    logger.debug(request)
    abi_hash = get_abi_hash(ABI_FILEPATH)
    return construct_ok_response(data=abi_hash)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'ima-abi'), methods=['GET'])
def ima_abi():
    logger.debug(request)
    abi_hash = get_abi_hash(MAINNET_IMA_ABI_FILEPATH)
    return construct_ok_response(data=abi_hash)


@node_bp.route(get_api_url(BLUEPRINT_NAME, 'can-update'), methods=['GET'])
@g_skale
def update_possible():
    logger.debug(request)
    possible = is_update_possible(g.skale, g.config, g.docker_utils)
    return construct_ok_response(data={'can_update': possible})
