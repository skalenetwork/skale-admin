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
from skale.types.node import NodeId
from skale.types.dkg import G2Point

from core.config.mirage.mirage_chain_node import MirageChainNodeInfo, generate_mirage_chain_nodes
from core.config.schain.static_params import get_mirage_chain_name
from core.dkg.utils import get_secret_key_share_filepath
from tools.configs import SGX_SSL_CERT_FILEPATH, SGX_SSL_KEY_FILEPATH
from tools.helper import read_json


@dataclass
class BlsKey:
    n: int
    common_bls_public_key: list[str]
    bls_public_key: list[str]

    key_share_name: str | None
    t: int | None
    cert_file: str | None
    key_file: str | None

    def to_dict(self):
        result: dict = {
            'n': self.n,
        }

        for i, key in enumerate(self.common_bls_public_key):
            result[f'commonBLSPublicKey{i}'] = str(key)

        for i, key in enumerate(self.bls_public_key):
            result[f'BLSPublicKey{i}'] = key

        if self.key_share_name is not None:
            result['keyShareName'] = self.key_share_name
        if self.t is not None:
            result['t'] = self.t
        if self.cert_file is not None:
            result['certFile'] = self.cert_file
        if self.key_file is not None:
            result['keyFile'] = self.key_file

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


def generate_committee_bls_key(
    committee_index: int,
    is_committee_node: bool,
    n: int,
    common_bls_public_key: list[str],
) -> BlsKey:
    # todod: handle the case for passive nodes
    if not is_committee_node:
        return BlsKey(
            key_share_name='',  # todod
            t=1,  # todod
            n=n,
            cert_file=SGX_SSL_CERT_FILEPATH,
            key_file=SGX_SSL_KEY_FILEPATH,
            common_bls_public_key=common_bls_public_key,
            bls_public_key=['0', '0', '1', '0'],
        )

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


# todod: move from here
def get_common_bls_public_key(common_bls_public_key: G2Point) -> list[str]:
    return [elem for coord in common_bls_public_key for elem in coord]


def generate_committee_info(
    committee_info_from_manager: list[CommitteeGroup],
    node_id: NodeId,
) -> Dict[int, CommitteeInfo]:
    committee_info = {}
    for committee in committee_info_from_manager:
        ts = committee['ts']
        committee_group = committee['group']
        index = committee['index']

        is_committee_node = any(node.id == node_id for node in committee_group)
        common_bls_public_key = committee['committee'].common_public_key

        bls_key = generate_committee_bls_key(
            index,
            is_committee_node,
            len(committee_group),
            get_common_bls_public_key(common_bls_public_key),
        )

        mirage_chain_nodes = generate_mirage_chain_nodes(committee_group, index, is_committee_node)
        committee_info[ts] = CommitteeInfo(bls_key=bls_key, group=mirage_chain_nodes)

    return committee_info
