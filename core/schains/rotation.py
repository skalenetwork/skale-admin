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
import shutil

from tools.configs import NODE_DATA_PATH


logger = logging.getLogger(__name__)


class ExitRequestError(Exception):
    pass


class ExitScheduleFileManager:
    def __init__(self, schain_name: str) -> None:
        self.schain_name = schain_name
        self.path = os.path.join(NODE_DATA_PATH, 'schains', schain_name, 'rotation.txt')

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def rm(self) -> bool:
        return os.remove(self.path)

    @property
    def exit_ts(self) -> int:
        with open(self.path) as exit_schedule_file:
            return json.load(exit_schedule_file)['timestamp']

    @exit_ts.setter
    def exit_ts(self, ts: int) -> None:
        tmp_path = os.path.join(os.path.dirname(self.path), '.rotation.txt.tmp')
        with open(tmp_path, 'w') as filepath:
            json.dump({'timestamp': ts}, filepath)
        shutil.move(tmp_path, self.path)


def set_rotation_for_schain(url: str, timestamp: int) -> None:
    _send_rotation_request(url, timestamp)


def _send_rotation_request(url, timestamp):
    logger.info(f'Sending rotation request: {timestamp}')
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
        raise ExitRequestError(response['error']['message'])


def get_schain_public_key(skale, schain_name):
    group_idx = skale.schains.name_to_id(schain_name)
    raw_public_key = skale.key_storage.get_previous_public_key(group_idx)
    public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    if public_key_array == ['0', '0', '1', '0']:  # zero public key
        raw_public_key = skale.key_storage.get_common_public_key(group_idx)
        public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    return ':'.join(map(str, public_key_array))
