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
from http import HTTPStatus
from datetime import datetime

from flask import Blueprint, g, request
from skale import FairManager

from core.checks.fair import FairConfigChecks, SkaledChecks
from core.config.schain.static_params import get_fair_chain_name
from core.firewall.utils import get_fair_committee_scope_rule_controller
from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from tools.configs import SYNC_NODE
from tools.docker_utils import DockerUtils
from web.helper import construct_err_response, construct_ok_response, g_fair, get_api_url

logger = logging.getLogger(__name__)

BLUEPRINT_NAME = 'fair-chain'
fair_chain_bp = Blueprint(BLUEPRINT_NAME, __name__)


def serialize_chain_record(chain_record: ChainRecord) -> dict:
    record_dict = chain_record.to_dict()
    for field_name, value in record_dict.items():
        if isinstance(value, datetime):
            record_dict[field_name] = value.timestamp()
    return record_dict


@fair_chain_bp.route(get_api_url(BLUEPRINT_NAME, 'record'), methods=['GET'])
def record():
    logger.debug(request)
    node_config: NodeConfig = g.config
    if not node_config.id:
        return construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )
    chain_name = get_fair_chain_name()
    chain_record = ChainRecord(chain_name)
    return construct_ok_response({'record': serialize_chain_record(chain_record)})


@fair_chain_bp.route(get_api_url(BLUEPRINT_NAME, 'checks'), methods=['GET'])
@g_fair
def checks():
    logger.debug(request)
    fair: FairManager = g.fair
    node_config: NodeConfig = g.config
    dutils: DockerUtils = g.docker_utils

    if not node_config.id:
        return construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )

    stream_version = get_skale_node_version()
    chain_name = get_fair_chain_name()
    chain_record = ChainRecord(chain_name)

    last_committee_index = fair.committee.last_committee_index()
    last_committee = fair.committee.get_committee(last_committee_index)

    rule_controller = get_fair_committee_scope_rule_controller()

    config_checks = FairConfigChecks(
        fair=fair,
        node_config=node_config,
        chain_name=chain_name,
        stream_version=stream_version,
        dkg_id=last_committee.dkg_id,
        chain_record=chain_record,
    )
    skaled_checks = SkaledChecks(
        chain_name=chain_name,
        chain_record=chain_record,
        rule_controller=rule_controller,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )
    return construct_ok_response(
        {
            'config_checks': config_checks.get_all(log=False),
            'skaled_checks': skaled_checks.get_all(log=False),
        }
    )
