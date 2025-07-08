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
import sys

from skale.types.dkg import DkgId, Status

from core.dkg.mirage.broadcast_filter import MirageFilter
from core.dkg.client import BaseDKGClient
from core.dkg.mirage.utils import (
    generate_mirage_bls_key_name,
    generate_mirage_poly_name,
)
from core.dkg.utils import convert_g2_points_to_array
from tools.configs import NODE_DATA_PATH

sys.path.insert(0, NODE_DATA_PATH)

logger = logging.getLogger(__name__)

class MirageDKGClient(BaseDKGClient):
    def __init__(
        self,
        node_id_dkg,
        node_id_contract,
        skale,
        t,
        n,
        public_keys,
        node_ids_dkg,
        node_ids_contract,
        eth_key_name,
        rotation_id,
        step
    ):
        super().__init__(
            node_id_dkg, node_id_contract, skale, t, n, public_keys,
            node_ids_dkg, node_ids_contract, eth_key_name, rotation_id, step
        )
        self.schain_bls_key_name = generate_mirage_bls_key_name(self.node_id_dkg, rotation_id)
        self.schain_poly_name = generate_mirage_poly_name(self.node_id_dkg, rotation_id)
    
    def get_round_status(self) -> Status:
        """Get the status of the DKG round."""
        return self.skale.dkg.get_round(DkgId(self.committee_id)).status

    def is_node_broadcasted(self) -> bool:
        return self.skale.dkg.is_node_broadcasted(
            DkgId(self.committee_id), self.node_id_dkg
        )

    def _send_broadcast_transaction(self):
        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()

        self.skale.dkg.broadcast(
            DkgId(self.committee_id),
            verification_vector,
            convert_g2_points_to_array(secret_key_contribution)
        )

    def _send_alright_transaction(self):
        self.skale.dkg.alright(DkgId(self.committee_id), self.node_id_contract)

    def get_broadcast_filter(self) -> MirageFilter:
        return MirageFilter(self.skale, self.committee_id, self.n)
    
    def is_everyone_broadcasted(self) -> bool:
        round_status = self.get_round_status()
        return round_status != Status.BROADCAST
    
    def get_common_bls_public_key(self) -> list[str]:
        raw_common_public_key = self.skale.dkg.get_round(DkgId(self.committee_id)).publicKey
        return [elem for coord in raw_common_public_key for elem in coord]
    
    def check_round_id(self) -> bool:
        """Check if the round ID matches the current committee ID."""
        return self.committee_id == self.skale.dkg.get_last_dkg_id()
    
    def is_broadcast_possible(self) -> bool:
        return not self.is_node_broadcasted() and self.check_round_id()
    
    def is_alright_possible(self) -> bool:
        """Check if the 'alright' transaction can be sent."""
        round_status = self.get_round_status()
        return round_status == Status.ALRIGHT and self.check_round_id()