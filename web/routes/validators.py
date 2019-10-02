#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from http import HTTPStatus

from flask import Blueprint, request
from playhouse.shortcuts import model_to_dict
from web.helper import construct_ok_response, login_required
from core.db import BountyEvent, BountyReceipt
from tools.configs import DATETIME_FORMAT

from core.node.utils import get_node_id

logger = logging.getLogger(__name__)


def construct_validators_bp(skale, config, wallet):
    validators_bp = Blueprint('validators', __name__)

    @validators_bp.route('/bounty-info', methods=['GET'])
    @login_required
    def bounty_info():
        logger.debug(request)
        events = BountyEvent.select(BountyEvent, BountyReceipt).join(BountyReceipt).execute()
        events_list = []
        for event in events:
            event_dict = model_to_dict(event, backrefs=True)
            event_dict['tx_dt'] = event_dict['tx_dt'].strftime(DATETIME_FORMAT)
            event_dict['stamp'] = event_dict['stamp'].strftime(DATETIME_FORMAT)
            events_list.append(event_dict)
        return construct_ok_response({'events': events_list})

    @validators_bp.route('/validators-info', methods=['GET'])
    @login_required
    def validators_info():
        logger.debug(request)

        node_id = get_node_id(config)
        # todo: handle no node_id

        print(skale.validators_data.get_validated_array)

        res = skale.validators_data.get_validated_array(node_id, wallet.get()['address'])
        print(res)

        validators = {
            'validating': res,
            'validated_by': 2
        }

        return construct_ok_response({'validators': validators})

    return validators_bp
