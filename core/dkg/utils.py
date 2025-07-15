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
from typing import NamedTuple

from eth_typing import HexStr
from eth_utils.hexadecimal import remove_0x_prefix

from skale.contracts.manager.dkg import G2Point, KeyShare
from skale.utils.helper import split_public_key

from core.dkg.structures import DKGStep

from tools.configs import NODE_DATA_PATH
from tools.helper import write_json

logger = logging.getLogger(__name__)

UINT_CONSTANT = 2**256 - 1
BROADCAST_DATA_SEARCH_SLEEP = 30


class DkgError(Exception):
    pass


class DkgTransactionError(DkgError):
    pass


class DkgVerificationError(DkgError):
    pass


class SgxDkgPolynomGenerationError(DkgError):
    pass


class DkgFailedError(DkgError):
    pass


class DKGKeyGenerationError(DkgError):
    pass


class BroadcastResult(NamedTuple):
    received: list[bool]
    correct: list[bool]


def get_secret_key_share_filepath(schain_name, rotation_id):
    return os.path.join(NODE_DATA_PATH, 'schains', schain_name, f'secret_key_{rotation_id}.json')


def save_dkg_results(dkg_results, filepath):
    """Save DKG results to the JSON file on disk"""
    write_json(filepath, dkg_results)


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


def sync_broadcast_data(dkg_client, dkg_filter, is_received, is_correct, broadcasts_found):
    if dkg_client.is_everyone_broadcasted():
        events = dkg_filter.get_events(from_channel_started_block=True)
    else:
        events = dkg_filter.get_events()
    for event in events:
        from_node = dkg_client.node_ids_contract[event.nodeIndex]
        if is_received[from_node] and from_node != dkg_client.node_id_dkg:
            continue
        else:
            is_received[from_node] = True
        broadcasted_data = [event.verificationVector, event.secretKeyContribution]
        is_received[from_node] = True
        try:
            dkg_client.receive_from_node(from_node, broadcasted_data)
            is_correct[from_node] = True
            broadcasts_found.append(event.nodeIndex)
        except DkgVerificationError as e:
            logger.error(e)
            continue
    return (is_received, is_correct, broadcasts_found)
