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

from dataclasses import dataclass


@dataclass
class PreviousKeyInfo:
    """Dataclass that contains info about previous public keys"""
    raw_bls_public_key: dict
    leaving_node_ecdsa_public_key: str
    new_node_ecdsa_public_key: str
    finish_ts: str

    @property
    def bls_public_key(self) -> dict:
        return _compose_bls_public_key_info(self.raw_bls_public_key)

    def to_dict(self):
        return {
            'blsPublicKey': self.bls_public_key,
            'leavingNodeEcdsaPublicKey': self.leaving_node_ecdsa_public_key,
            'newNodeEcdsaPublicKey': self.new_node_ecdsa_public_key,
            'finishTs': self.finish_ts,
        }


def _compose_bls_public_key_info(bls_public_key):
    return {
        'blsPublicKey0': str(bls_public_key[0][0]),
        'blsPublicKey1': str(bls_public_key[0][1]),
        'blsPublicKey2': str(bls_public_key[1][0]),
        'blsPublicKey3': str(bls_public_key[1][1])
    }


def compose_previous_keys_info(skale, rotation_data, previous_bls_keys) -> dict:
    previous_keys_info = []
    for idx, rotation in enumerate(rotation_data):
        leaving_node_ecdsa_public_key = skale.nodes.get_node_public_key(rotation['leaving_node'])
        new_node_ecdsa_public_key = skale.nodes.get_node_public_key(rotation['new_node'])

        previous_key_info = PreviousKeyInfo(
            raw_bls_public_key=previous_bls_keys[idx],
            leaving_node_ecdsa_public_key=leaving_node_ecdsa_public_key,
            new_node_ecdsa_public_key=new_node_ecdsa_public_key,
            finish_ts=rotation['finish_ts']
        )
        previous_keys_info.append(previous_key_info)
    return previous_keys_info


def previous_keys_info_to_dicts(previous_keys_info):
    return [
        previous_key_info.to_dict()
        for previous_key_info in previous_keys_info
    ]
