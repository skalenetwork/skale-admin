#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025-Present SKALE Labs
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
from typing import Dict

from skale.types.committee import CommitteeGroup

from core.config.mirage.mirage_chain_node import MirageChainNodeInfo, generate_mirage_chain_nodes
from core.config.schain.static_params import get_mirage_chain_name
from core.dkg.utils import get_secret_key_share_filepath
from tools.configs import SGX_SSL_CERT_FILEPATH, SGX_SSL_KEY_FILEPATH
from tools.helper import read_json


@dataclass
class BlsKey:
    key_share_name: str
    t: int
    n: int
    cert_file: str
    key_file: str
    common_bls_public_key: list[str]
    bls_public_key: list[str]

    def to_dict(self):
        result = {
            'keyShareName': self.key_share_name,
            't': self.t,
            'n': self.n,
            'certFile': self.cert_file,
            'keyFile': self.key_file,
        }

        for i, key in enumerate(self.common_bls_public_key):
            result[f'commonBLSPublicKey{i}'] = str(key)

        for i, key in enumerate(self.bls_public_key):
            result[f'BLSPublicKey{i}'] = key

        return result


@dataclass
class CommitteeInfo:
    bls_key: BlsKey
    group: list[MirageChainNodeInfo]

    def to_dict(self) -> dict:
        return {
            'blsKey': self.bls_key.to_dict(),
            'group': [node.to_dict() for node in self.group],
        }


def generate_committee_bls_key(committee_index: int) -> BlsKey:
    secret_key_share_filepath = get_secret_key_share_filepath(
        get_mirage_chain_name(), committee_index
    )
    secret_key_share_config = read_json(secret_key_share_filepath)

    return BlsKey(
        key_share_name=secret_key_share_config['key_share_name'],
        t=secret_key_share_config['t'],
        n=secret_key_share_config['n'],
        cert_file=SGX_SSL_CERT_FILEPATH,
        key_file=SGX_SSL_KEY_FILEPATH,
        common_bls_public_key=secret_key_share_config['common_public_key'],
        bls_public_key=secret_key_share_config['public_key'],
    )


def generate_committee_info(
    committee_info_from_manager: list[CommitteeGroup],
    sync_node: bool = False,
) -> Dict[int, CommitteeInfo]:
    committee_info = {}
    for committee in committee_info_from_manager:
        ts = committee['ts']
        committee_group = committee['group']
        index = committee['index']
        bls_key = generate_committee_bls_key(index)
        mirage_chain_nodes = generate_mirage_chain_nodes(committee_group, index, sync_node)
        committee_info[ts] = CommitteeInfo(bls_key=bls_key, group=mirage_chain_nodes)

    return committee_info
