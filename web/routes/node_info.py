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

from flask import Blueprint, g, request

from core.node import get_meta_info, get_node_hardware_info
from tools.configs.flask import SKALE_LIB_NAME
from tools.configs.web3 import ENDPOINT, UNTRUSTED_PROVIDERS
from tools.notifications.messages import tg_notifications_enabled, send_message
from tools.helper import init_skale
from web.helper import construct_ok_response, construct_err_response

logger = logging.getLogger(__name__)


def construct_node_info_bp():
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
        containers_list = g.docker_utils.get_all_skale_containers(all=all, format=True)
        return construct_ok_response(containers_list)

    @node_info_bp.route('/send-tg-notification', methods=['POST'])
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

    @node_info_bp.route('/about-node', methods=['GET'])
    def about_node():
        logger.debug(request)
        skale = init_skale(g.wallet)

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

    @node_info_bp.route('/hardware', methods=['GET'])
    def hardware():
        logger.debug(request)
        hardware_info = get_node_hardware_info()
        return construct_ok_response(hardware_info)

    @node_info_bp.route('/endpoint-info', methods=['GET'])
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

    @node_info_bp.route('/meta-info', methods=['GET'])
    def meta_info():
        logger.debug(request)
        version_data = get_meta_info()
        return construct_ok_response(version_data)

    return node_info_bp
