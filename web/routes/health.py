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
from http import HTTPStatus

from flask import Blueprint, Response, g, request
from skale import SkaleManager

from core.checks.schain import SChainChecks
from core.firewall.utils import get_default_rule_controller
from core.ima.container import get_ima_log_checks
from core.manager_cache import ManagerCache
from core.node import get_current_nodes, get_skale_node_version
from core.schains.external_config import ExternalState
from core.schains.process import is_process_healthy
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from web.helper import (
    construct_err_response,
    construct_ok_response,
    g_manager_cache,
    g_skale,
    get_api_url,
)
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)
BLUEPRINT_NAME = 'health'


health_bp = Blueprint(BLUEPRINT_NAME, __name__)


@health_bp.route(get_api_url(BLUEPRINT_NAME, 'schains'), methods=['GET'])
@g_skale
@g_manager_cache
def schains_checks() -> Response:
    logger.debug(request)
    checks_filter_raw = request.args.get('checks_filter')
    checks_filter: list[str] | None = None
    if checks_filter_raw:
        checks_filter = checks_filter_raw.split(',')
    node_id = g.config.id
    if node_id is None:
        return construct_err_response(status_code=HTTPStatus.BAD_REQUEST, msg='No node installed')

    manager_cache: ManagerCache = g.manager_cache
    skale: SkaleManager = g.skale

    allowed_diff = int(manager_cache.dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    stream_version = get_skale_node_version()
    estate = ExternalState(chain_id=skale.web3.eth.chain_id, ima_linked=True, ranges=[])
    checks = []
    for schain in manager_cache.schains:
        if schain.name != '':
            rotation_data = skale.node_rotation.get_rotation(schain.name)
            rotation_id = rotation_data.rotation_counter
            if SChainRecord.added(schain.name):
                rc = get_default_rule_controller(
                    name=schain.name, sync_agent_ranges=manager_cache.sync_ranges
                )
                current_nodes = get_current_nodes(g.skale, schain.schain_hash, manager_cache)
                schain_record = SChainRecord.get_by_name(schain.name)
                schain_checks = SChainChecks(
                    schain.name,
                    node_id,
                    schain_record=schain_record,
                    rule_controller=rc,
                    rotation_id=rotation_id,
                    stream_version=stream_version,
                    current_nodes=current_nodes,
                    last_dkg_successful=True,
                    estate=estate,
                    passive_node=False,
                ).get_all(needed=checks_filter)
                if not checks_filter or 'process' in checks_filter:
                    schain_checks.update(
                        {'process': is_process_healthy(schain.name, allowed_diff=allowed_diff)}
                    )

                checks.append({'name': schain.name, 'healthchecks': schain_checks})
    return construct_ok_response(checks)


@health_bp.route(get_api_url(BLUEPRINT_NAME, 'ima'), methods=['GET'])
def ima_log_checks():
    logger.debug(request)
    node_id = g.config.id
    if node_id is None:
        return construct_err_response(status_code=HTTPStatus.BAD_REQUEST, msg='No node installed')
    checks = get_ima_log_checks()
    return construct_ok_response(checks)
