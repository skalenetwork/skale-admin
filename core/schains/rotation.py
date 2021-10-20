#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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

import json
import logging
import requests

from core.schains.config.helper import get_skaled_http_address


logger = logging.getLogger(__name__)


def set_rotation_for_schain(schain_name: str, timestamp: int) -> None:
    endpoint = get_skaled_http_address(schain_name)
    url = f'http://{endpoint.ip}:{endpoint.port}'
    _send_rotation_request(url, timestamp)


def _send_rotation_request(url, timestamp):
    logger.info(f'Send rotation request: {timestamp}')
    headers = {'content-type': 'application/json'}
    data = {
        'finishTime': timestamp
    }
    call_data = {
        "id": 0,
        "jsonrpc": "2.0",
        "method": "setSchainExitTime",
        "params": data,
    }
    response = requests.post(
        url=url,
        data=json.dumps(call_data),
        headers=headers,
    ).json()
    if response.get('error'):
        raise Exception(response['error']['message'])
