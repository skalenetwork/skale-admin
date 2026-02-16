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

from flask import Blueprint, g, request
from sgx import SgxClient
from skale_core.settings import ActiveSettings, BaseNodeSettings

from core.node import get_btrfs_info, get_check_report, get_meta_info, get_node_hardware_info
from tools.constants.web3 import UNTRUSTED_PROVIDERS
from tools.helper import get_endpoint_call_speed
from tools.sgx_utils import SGX_CERTIFICATES_FOLDER
from web.helper import construct_ok_response, g_web3, get_api_url

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'info'


info_bp = Blueprint(BLUEPRINT_NAME, __name__)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'hardware'), methods=['GET'])
def hardware():
    logger.debug(request)
    hardware_info = get_node_hardware_info()
    return construct_ok_response(hardware_info)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'endpoint-info'), methods=['GET'])
@g_web3
def endpoint_info():
    logger.debug(request)
    call_speed = get_endpoint_call_speed(g.web3)
    block_number = g.web3.eth.block_number
    st: BaseNodeSettings = g.st
    endpoint = str(st.endpoint)
    trusted = not any([untrusted in endpoint for untrusted in UNTRUSTED_PROVIDERS])
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
        'syncing': syncing,
    }
    logger.info(f'endpoint info: {info}')
    return construct_ok_response(info)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'meta-info'), methods=['GET'])
def meta_info():
    logger.debug(request)
    version_data = get_meta_info()
    return construct_ok_response(version_data)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'btrfs-info'), methods=['GET'])
def btrfs_info():
    logger.debug(request)
    btrfs_data = get_btrfs_info()
    return construct_ok_response(btrfs_data)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'sgx'), methods=['GET'])
def sgx_info():
    logger.debug(request)
    status_zmq = False
    status_https = False
    version = None
    st: ActiveSettings = g.st
    sgx = SgxClient(str(st.sgx_url), SGX_CERTIFICATES_FOLDER, zmq=True)
    try:
        if sgx.zmq.get_server_status() == 0:
            status_zmq = True
        version = sgx.zmq.get_server_version()
    except Exception as err:
        logger.error(f'Cannot make SGX ZMQ check {err}')
    sgx_https = SgxClient(str(st.sgx_url), SGX_CERTIFICATES_FOLDER)
    try:
        if sgx_https.get_server_status() == 0:
            status_https = True
        if version is None:
            version = sgx_https.get_server_version()
    except Exception as err:
        logger.error(f'Cannot make SGX HTTPS check {err}')

    res = {
        'status_zmq': status_zmq,
        'status_https': status_https,
        'sgx_server_url': str(st.sgx_url),
        'sgx_keyname': g.config.sgx_key_name,
        'sgx_wallet_version': version,
    }
    return construct_ok_response(data=res)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'check-report'), methods=['GET'])
def check_report():
    logger.debug(request)
    report = get_check_report()
    return construct_ok_response(data=report)


@info_bp.route(get_api_url(BLUEPRINT_NAME, 'containers'), methods=['GET'])
def containers():
    logger.debug(request)
    all = request.args.get('all') == 'True'
    name_filter = request.args.get('name_filter') or ''
    containers_list = g.docker_utils.get_containers_info(
        all=all, name_filter=name_filter, format=True
    )
    return construct_ok_response(containers_list)
