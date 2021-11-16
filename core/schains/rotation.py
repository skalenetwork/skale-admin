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

import os
import json
import logging
import requests

from core.schains.config.directory import get_schain_rotation_filepath
from core.schains.runner import is_exited_with_zero
from core.schains.config.helper import get_skaled_http_address
from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


def set_rotation_for_schain(schain_name: str, timestamp: int) -> None:
    url = get_skaled_http_address(schain_name)
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


def check_schain_rotated(schain_name, dutils=None):
    dutils = dutils or DockerUtils()
    schain_rotation_filepath = get_schain_rotation_filepath(schain_name)
    rotation_file_exists = os.path.exists(schain_rotation_filepath)
    zero_exit_code = is_exited_with_zero(schain_name, dutils=dutils)
    return rotation_file_exists and zero_exit_code


def get_schain_public_key(skale, schain_name):
    group_idx = skale.schains.name_to_id(schain_name)
    raw_public_key = skale.key_storage.get_previous_public_key(group_idx)
    public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    if public_key_array == ['0', '0', '1', '0']:  # zero public key
        raw_public_key = skale.key_storage.get_common_public_key(group_idx)
        public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    return ':'.join(map(str, public_key_array))
