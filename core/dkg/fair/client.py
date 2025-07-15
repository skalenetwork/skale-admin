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

from core.dkg.fair.broadcast_filter import FairFilter
from core.dkg.client import BaseDKGClient
from core.dkg.structures import DKGStep
from core.dkg.utils import DkgVerificationError, SgxDkgPolynomGenerationError, to_verify

from sgx.http import SgxUnreachableError
from sgx.sgx_rpc_handler import DkgPolyStatus

from tools.configs import NODE_DATA_PATH
from tools.sgx_utils import sgx_unreachable_retry

sys.path.insert(0, NODE_DATA_PATH)

logger = logging.getLogger(__name__)


def generate_fair_poly_name(node_id, rotation_id):
    return f'POLY:SCHAIN_ID:42653616163153870673020210111455690314811246121842211213597906712792875697871:NODE_ID:{str(node_id)}:DKG_ID:{str(rotation_id)}'  # noqa


def generate_fair_bls_key_name(node_id, rotation_id):
    return f'BLS_KEY:SCHAIN_ID:42653616163153870673020210111455690314811246121842211213597906712792875697877:NODE_ID:{str(node_id)}:DKG_ID:{str(rotation_id)}'  # noqa


class FairDKGClient(BaseDKGClient):
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
        step: DKGStep = DKGStep.NONE,
    ):
        super().__init__(
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
            step,
        )
        self.broadcast_filter = FairFilter(self.skale, self.rotation_id, self.n)
        self.bls_name = generate_fair_bls_key_name(self.node_id_dkg, rotation_id)
        self.poly_name = generate_fair_poly_name(self.node_id_dkg, rotation_id)

    def get_round_status(self) -> Status:
        """Get the status of the DKG round."""
        return self.skale.dkg.get_round(DkgId(self.rotation_id)).status

    def is_node_broadcasted(self) -> bool:
        return self.skale.dkg.is_node_broadcasted(DkgId(self.rotation_id), self.node_id_contract)

    def is_node_sent_alright(self) -> bool:
        return self.skale.dkg.is_node_sent_alright(DkgId(self.rotation_id), self.node_id_dkg)

    def receive_from_node(self, from_node, broadcasted_data):
        if from_node != self.node_id_dkg:
            logger.info(f'Receiving from node {from_node}')
        self.store_broadcasted_data(broadcasted_data, from_node)
        if from_node == self.node_id_dkg:
            return

        try:
            if not self.verification(from_node):
                raise DkgVerificationError(
                    f'Fatal error : user {str(from_node + 1)} '
                    f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                )
            logger.info(f'All data from {from_node} was received and verified')
        except SgxUnreachableError as e:
            raise SgxUnreachableError(
                f'Fatal error : user {str(from_node + 1)} '
                f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                f'with SgxUnreachableError: ',
                e,
            )

    def _send_broadcast_transaction(self):
        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()

        logger.info(
            f'DKGClient is going to broadcast with vv {verification_vector}, skc {secret_key_contribution}'  # noqa
        )

        self.skale.dkg.broadcast(
            DkgId(self.rotation_id), verification_vector, secret_key_contribution
        )

    def _send_alright_transaction(self):
        self.skale.dkg.alright(DkgId(self.rotation_id))

    def get_broadcast_filter(self) -> FairFilter:
        return self.broadcast_filter

    def is_everyone_broadcasted(self) -> bool:
        round_status = self.get_round_status()
        return round_status != Status.BROADCAST

    def get_common_bls_public_key(self) -> list[str]:
        raw_common_public_key = self.skale.dkg.get_round(DkgId(self.rotation_id)).publicKey
        return [elem for coord in raw_common_public_key for elem in coord]

    def check_round_id(self) -> bool:
        """Check if the round ID matches the current rotation ID."""
        return self.rotation_id == self.skale.dkg.get_last_dkg_id()

    def is_broadcast_possible(self) -> bool:
        return not self.is_node_broadcasted() and self.check_round_id()

    def is_alright_possible(self) -> bool:
        """Check if the 'alright' transaction can be sent."""
        round_status = self.get_round_status()
        return (
            not self.is_node_sent_alright()
            and round_status == Status.ALRIGHT
            and self.check_round_id()
        )

    @sgx_unreachable_retry
    def generate_bls_key(self):
        received_secret_key_contribution = ''.join(
            to_verify(self.incoming_secret_key_contribution[j]) for j in range(self.sgx.n)
        )
        logger.info(
            f'DKGClient is going to create BLS private key with name {self.bls_name}'
        )
        bls_private_key = self.sgx.create_bls_private_key_v2(
            self.poly_name, self.bls_name, self.eth_key_name, received_secret_key_contribution
        )
        logger.info(
            f'DKGClient is going to fetch BLS public key with name {self.bls_name}'
        )
        self.public_key = self.sgx.get_bls_public_key(self.bls_name)
        return bls_private_key

    def fetch_all_broadcasted_data(self):
        dkg_filter = self.get_broadcast_filter()
        events = dkg_filter.get_events()

        for event in events:
            from_node = self.node_ids_contract[event.nodeIndex]
            broadcasted_data = [event.verificationVector, event.secretKeyContribution]
            self.store_broadcasted_data(broadcasted_data, from_node)
            logger.info(
                f'Received by {self.node_id_dkg} from {from_node}'
            )

    def broadcast(self):
        poly_success = self.generate_polynomial(self.poly_name)
        if poly_success == DkgPolyStatus.FAIL:
            raise SgxDkgPolynomGenerationError('Sgx dkg polynom generation failed')

        if not self.is_broadcast_possible():
            return

        self._send_broadcast_transaction()
        logger.info('Everything is sent from %d node', self.node_id_dkg)
        self.last_completed_step = DKGStep.BROADCAST
