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

from flask import Blueprint, g, request

from core.schains.config.directory import schain_config_exists
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_schain_config
)
from core.schains.firewall.utils import (
    get_default_rule_controller,
    get_sync_agent_ranges
)
from core.schains.skaled_status import init_skaled_status
from core.schains.ima import get_ima_version
from core.schains.info import get_schain_info_by_name, get_skaled_version
from core.schains.cleaner import get_schains_on_node
from web.models.schain import get_schains_statuses, toggle_schain_repair_mode
from web.helper import (
    construct_ok_response,
    construct_err_response,
    construct_key_error_response,
    get_api_url,
    g_skale
)


logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'schains'


def construct_schains_bp():
    schains_bp = Blueprint(BLUEPRINT_NAME, __name__)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'statuses'), methods=['GET'])
    def schain_statuses():
        logger.debug(request)
        node_id = g.config.id
        if node_id is None:
            return construct_err_response(msg='No node installed')
        schains_on_node = get_schains_on_node(g.docker_utils)
        statuses = {}
        for schain_name in schains_on_node:
            skaled_status = init_skaled_status(schain_name)
            statuses[schain_name] = skaled_status.all
        return construct_ok_response(statuses)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'config'), methods=['GET'])
    def schain_config():
        logger.debug(request)
        key = 'schain_name'
        schain_name = request.args.get(key)
        if not schain_name:
            return construct_key_error_response([key])
        schain_config = get_schain_config(schain_name)
        if schain_config is None:
            return construct_err_response(
                msg=f'sChain config not found: {schain_name}'
            )
        skale_schain_config = schain_config['skaleConfig']
        return construct_ok_response(skale_schain_config)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'list'), methods=['GET'])
    @g_skale
    def schains_list():
        logger.debug(request)
        logger.debug(request)
        node_id = g.config.id
        if node_id is None:
            return construct_err_response(msg='No node installed')
        schains_list = list(filter(
            lambda s: s.get('name'),
            g.skale.schains.get_schains_for_node(node_id)
        ))
        return construct_ok_response(schains_list)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'dkg-statuses'), methods=['GET'])
    def dkg_statuses():
        logger.debug(request)
        _all = request.args.get('all') == 'True'
        dkg_statuses = get_schains_statuses(_all)
        return construct_ok_response(dkg_statuses)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'firewall-rules'), methods=['GET'])
    @g_skale
    def firewall_rules():
        logger.debug(request)
        schain_name = request.args.get('schain_name')
        sync_agent_ranges = get_sync_agent_ranges(g.skale)
        if not schain_config_exists(schain_name):
            return construct_err_response(
                msg=f'No schain with name {schain_name}'
            )
        conf = get_schain_config(schain_name)
        base_port = get_base_port_from_config(conf)
        node_ips = get_node_ips_from_config(conf)
        own_ip = get_own_ip_from_config(conf)

        rc = get_default_rule_controller(
            schain_name,
            base_port,
            own_ip,
            node_ips,
            sync_agent_ranges
        )
        endpoints = [e._asdict() for e in rc.actual_rules()]
        return construct_ok_response({'endpoints': endpoints})

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'repair'), methods=['POST'])
    def repair():
        logger.debug(request)
        schain_name = request.json.get('schain_name')
        result = toggle_schain_repair_mode(schain_name)
        if result:
            return construct_ok_response()
        else:
            return construct_err_response(
                msg=f'No schain with name {schain_name}'
            )

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'get'), methods=['GET'])
    @g_skale
    def get_schain():
        logger.debug(request)
        schain_name = request.args.get('schain_name')
        info = get_schain_info_by_name(g.skale, schain_name)
        if not info:
            return construct_err_response(
                msg=f'No schain with name {schain_name}'
            )
        response = info.to_dict()
        return construct_ok_response(response)

    @schains_bp.route(get_api_url(BLUEPRINT_NAME, 'container-versions'), methods=['GET'])
    def schain_containers_versions():
        logger.debug(request)
        version_data = {
            'skaled_version': get_skaled_version(),
            'ima_version': get_ima_version()
        }
        return construct_ok_response(version_data)

    return schains_bp
