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
import os

from eth_typing import HexStr
from eth_utils.hexadecimal import remove_0x_prefix

from skale.contracts.manager.dkg import G2Point, KeyShare
from skale.utils.helper import split_public_key

from tools.configs import NODE_DATA_PATH

logger = logging.getLogger(__name__)

def get_secret_key_share_filepath(schain_name, rotation_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_name, f'secret_key_{rotation_id}.json')


def convert_g2_points_to_array(data):
    g2_array = []
    for point in data:
        new_point = []
        for coord in point:
            new_coord = int(coord)
            new_point.append(new_coord)
        new_g2_point = G2Point((new_point[0], new_point[1]), (new_point[2], new_point[3]))
        g2_array.append(new_g2_point)
    return g2_array


def convert_g2_array_to_hex(data):
    data_hexed = ''
    for point in data:
        data_hexed += convert_g2_point_to_hex(point)
    return data_hexed


def convert_g2_point_to_hex(data):
    data_hexed = ''
    for coord in data:
        temp = remove_0x_prefix(HexStr(hex(int(coord))))
        while len(temp) < 64:
            temp = '0' + temp
        data_hexed += temp
    return data_hexed


def convert_hex_to_g2_array(data):
    g2_array = []
    while len(data) > 0:
        cur = data[:256]
        g2_array.append([str(x) for x in [int(cur[64 * i : 64 * i + 64], 16) for i in range(4)]])  # noqa
        data = data[256:]
    return g2_array


def convert_str_to_key_share(sent_secret_key_contribution, n):
    return_value = []
    for i in range(n):
        public_key = sent_secret_key_contribution[i * 192 + 64 : (i + 1) * 192]  # noqa
        key_share = bytes.fromhex(sent_secret_key_contribution[i * 192 : i * 192 + 64])  # noqa
        return_value.append(KeyShare(split_public_key(public_key), key_share))
    return return_value


def convert_key_share_to_str(data, n):
    return ''.join(to_verify(s) for s in [data[i * 192 : (i + 1) * 192] for i in range(n)])  # noqa


def to_verify(share):
    return share[128:192] + share[:128]
