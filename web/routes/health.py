#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2020 SKALE Labs
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
from enum import Enum
from http import HTTPStatus


from flask import Blueprint, g, request
from sgx import SgxClient


from core.node import get_check_report
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_log_checks
from tools.sgx_utils import SGX_SERVER_URL
from tools.configs import SGX_CERTIFICATES_FOLDER
from tools.helper import init_skale
from web.models.schain import SChainRecord
from web.helper import (
    construct_err_response,
    construct_ok_response,
    get_api_url
)

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'health'


class SGXStatus(Enum):
    CONNECTED = 0
    NOT_CONNECTED = 1


def construct_health_bp():
    health_bp = Blueprint(BLUEPRINT_NAME, __name__)

    @health_bp.route(get_api_url(BLUEPRINT_NAME, 'containers'), methods=['GET'])
    def containers():
        logger.debug(request)
        all = request.args.get('all') == 'True'
        name_filter = request.args.get('name_filter') or ''
        containers_list = g.docker_utils.get_containers_info(
            all=all,
            name_filter=name_filter,
            format=True
        )
        return construct_ok_response(containers_list)

    @health_bp.route(get_api_url(BLUEPRINT_NAME, 'schains'), methods=['GET'])
    def schains_checks():
        logger.debug(request)
        skale = init_skale(wallet=g.wallet)
        node_id = g.config.id
        if node_id is None:
            return construct_err_response(status_code=HTTPStatus.BAD_REQUEST,
                                          msg='No node installed')

        schains = skale.schains.get_schains_for_node(node_id)
        checks = []
        for schain in schains:
            if schain.get('name') != '':
                rotation_data = skale.node_rotation.get_rotation(schain['name'])
                rotation_id = rotation_data['rotation_id']
                if SChainRecord.added(schain['name']):
                    schain_record = SChainRecord.get_by_name(schain['name'])
                    schain_checks = SChainChecks(
                        schain['name'],
                        node_id,
                        schain_record=schain_record,
                        rotation_id=rotation_id
                    ).get_all()
                    checks.append({
                        'name': schain['name'],
                        'healthchecks': schain_checks
                    })
        return construct_ok_response(checks)

    @health_bp.route(get_api_url(BLUEPRINT_NAME, 'ima'), methods=['GET'])
    def ima_log_checks():
        logger.debug(request)
        node_id = g.config.id
        if node_id is None:
            return construct_err_response(status_code=HTTPStatus.BAD_REQUEST,
                                          msg='No node installed')
        checks = get_ima_log_checks()
        return construct_ok_response(checks)

    @health_bp.route(get_api_url(BLUEPRINT_NAME, 'sgx'), methods=['GET'])
    def sgx_info():
        logger.debug(request)
        sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
        try:
            status = sgx.get_server_status()
            version = sgx.get_server_version()
        except Exception:  # todo: catch specific error - edit sgx.py
            status = 1
            version = None
        res = {
            'status': status,
            'status_name': SGXStatus(status).name,
            'sgx_server_url': SGX_SERVER_URL,
            'sgx_keyname': g.config.sgx_key_name,
            'sgx_wallet_version': version
        }
        return construct_ok_response(data=res)

    @health_bp.route(
        get_api_url(BLUEPRINT_NAME, 'check-report'),
        methods=['GET']
    )
    def check_report():
        logger.debug(request)
        report = get_check_report()
        return construct_ok_response(data=report)

    return health_bp
