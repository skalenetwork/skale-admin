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
import sys

from sgx.http import SgxUnreachableError
from sgx.sgx_rpc_handler import DkgPolyStatus
from skale.contracts.manager.dkg import G2Point
from skale.transactions.result import TransactionFailedError

from core.dkg.client import BaseDKGClient
from core.dkg.schain.broadcast_filter import SchainFilter
from core.dkg.schain.structures import ComplaintReason
from core.dkg.structures import DKGStep
from core.dkg.utils import (
    DkgTransactionError,
    DkgVerificationError,
    SgxDkgPolynomGenerationError,
    convert_g2_points_to_array,
    convert_str_to_key_share,
    to_verify,
)
from tools.constants import NODE_DATA_PATH
from tools.sgx_utils import sgx_unreachable_retry

sys.path.insert(0, str(NODE_DATA_PATH))

logger = logging.getLogger(__name__)


class SchainDKGClient(BaseDKGClient):
    def __init__(
        self,
        node_id_dkg,
        node_id_contract,
        skale,
        t,
        n,
        chain_name,
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
            chain_name,
            step,
        )
        self.dkg_contract_functions = self.skale.dkg.contract.functions
        self.dkg_timeout = self.skale.constants_holder.get_dkg_timeout()
        self.complaint_error_event_hash = self.skale.web3.to_hex(
            self.skale.web3.keccak(text='ComplaintError(string)')
        )
        self.broadcast_filter = SchainFilter(self.skale, self.chain_name, self.n)
        logger.info(f'sChain: {self.chain_name}. DKG timeout is {self.dkg_timeout}')

    def is_channel_opened(self):
        return self.skale.dkg.is_channel_opened(self.group_index)

    def check_complaint_logs(self, logs):
        return logs['topics'][0].hex() != self.complaint_error_event_hash

    def is_node_broadcasted(self) -> bool:
        return self.skale.dkg.is_node_broadcasted(self.group_index, self.node_id_contract)

    def receive_from_node(self, from_node, broadcasted_data):
        if from_node != self.node_id_dkg:
            logger.info(f'sChain {self.chain_name}: receiving from node {from_node}')
        self.store_broadcasted_data(broadcasted_data, from_node)
        if from_node == self.node_id_dkg:
            return

        try:
            if not self.verification(from_node):
                raise DkgVerificationError(
                    f'sChain: {self.chain_name}. '
                    f'Fatal error : user {str(from_node + 1)} '
                    f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                )
            logger.info(
                f'sChain: {self.chain_name}. All data from {from_node} was received and verified'
            )
        except SgxUnreachableError as e:
            raise SgxUnreachableError(
                f'sChain: {self.chain_name}. '
                f'Fatal error : user {str(from_node + 1)} '
                f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                f'with SgxUnreachableError: ',
                e,
            )

    def send_complaint(self, to_node: int, reason: ComplaintReason):
        logger.info(
            f'sChain: {self.chain_name}. '
            f'{self.node_id_dkg} node is trying to sent a {reason} on {to_node} node'
        )

        is_complaint_possible = self.skale.dkg.is_complaint_possible(
            self.group_index,
            self.node_id_contract,
            self.node_ids_dkg[to_node],
            self.skale.wallet.address,
        )
        is_channel_opened = self.is_channel_opened()
        logger.info(
            'Complaint possible %s, channel opened %s', is_complaint_possible, is_channel_opened
        )

        if not is_complaint_possible or not is_channel_opened:
            logger.info('%d node could not sent a complaint on %d node', self.node_id_dkg, to_node)
            return False

        reason_to_step = {
            ComplaintReason.NO_BROADCAST: DKGStep.COMPLAINT_NO_BROADCAST,
            ComplaintReason.BAD_DATA: DKGStep.COMPLAINT_BAD_DATA,
            ComplaintReason.NO_ALRIGHT: DKGStep.COMPLAINT_NO_ALRIGHT,
            ComplaintReason.NO_RESPONSE: DKGStep.COMPLAINT_NO_RESPONSE,
        }

        try:
            if reason == ComplaintReason.BAD_DATA:
                tx_res = self.skale.dkg.complaint_bad_data(
                    self.group_index, self.node_id_contract, self.node_ids_dkg[to_node]
                )
            else:
                tx_res = self.skale.dkg.complaint(
                    self.group_index, self.node_id_contract, self.node_ids_dkg[to_node]
                )
            if self.check_complaint_logs(tx_res.receipt['logs'][0]):
                logger.info(
                    f'sChain: {self.chain_name}. '
                    f'{self.node_id_dkg} node sent a complaint on {to_node} node'
                )
                self.last_completed_step = reason_to_step[reason]
                return True
            else:
                logger.info(
                    f'sChain: {self.chain_name}. Complaint from {self.node_id_dkg} on '
                    f'{to_node} node was rejected'
                )
                return False
        except TransactionFailedError as e:
            logger.error(f'DKG complaint failed: sChain {self.chain_name}')
            raise DkgTransactionError(e)

    @sgx_unreachable_retry
    def get_complaint_response(self, to_node_index):
        response = self.sgx.complaint_response(
            self.poly_name, self.node_ids_contract[to_node_index]
        )
        share, dh_key = response.share, response.dh_key
        verification_vector_mult = response.verification_vector_mult
        share = share.split(':')
        for i in range(4):
            share[i] = int(share[i])
        share = G2Point((share[0], share[1]), (share[2], share[3]))
        return share, dh_key, verification_vector_mult

    def response(self, to_node_index):
        is_pre_response_possible = self.skale.dkg.is_pre_response_possible(
            self.group_index, self.node_id_contract, self.skale.wallet.address
        )

        if not is_pre_response_possible or not self.is_channel_opened():
            logger.info(
                f'sChain: {self.chain_name}. {self.node_id_dkg} node could not sent a response'
            )
            return

        share, dh_key, verification_vector_mult = self.get_complaint_response(to_node_index)

        try:
            self.skale.dkg.pre_response(
                self.group_index,
                self.node_id_contract,
                convert_g2_points_to_array(self.incoming_verification_vector[self.node_id_dkg]),
                convert_g2_points_to_array(verification_vector_mult),
                convert_str_to_key_share(self.sent_secret_key_contribution, self.n),
            )
            self.last_completed_step = DKGStep.PRE_RESPONSE

            is_response_possible = self.skale.dkg.is_response_possible(
                self.group_index, self.node_id_contract, self.skale.wallet.address
            )

            if not is_response_possible or not self.is_channel_opened():
                logger.info(
                    f'sChain: {self.chain_name}. {self.node_id_dkg} node could not sent a response'
                )
                return

            self.skale.dkg.response(self.group_index, self.node_id_contract, int(dh_key, 16), share)
            self.last_completed_step = DKGStep.RESPONSE
            logger.info(f'sChain: {self.chain_name}. {self.node_id_dkg} node sent a response')
        except TransactionFailedError as e:
            logger.error(f'DKG response failed: sChain {self.chain_name}')
            raise DkgTransactionError(e)

    def is_all_data_received(self, from_node):
        return self.skale.dkg.is_all_data_received(self.group_index, self.node_ids_dkg[from_node])

    def is_everyone_broadcasted(self) -> bool:
        return self.skale.dkg.is_everyone_broadcasted(self.group_index, self.skale.wallet.address)

    def is_everyone_sent_algright(self):
        return self.skale.dkg.get_number_of_completed(self.group_index) == self.n

    def get_broadcast_filter(self):
        return self.broadcast_filter

    def _send_broadcast_transaction(self):
        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()

        self.skale.dkg.broadcast(
            self.group_index,
            self.node_id_contract,
            verification_vector,
            secret_key_contribution,
            self.rotation_id,
        )

    def _send_alright_transaction(self):
        logger.info(f'sChain {self.chain_name} sending alright transaction')
        self.skale.dkg.alright(
            self.group_index, self.node_id_contract, gas_limit=1000000, multiplier=2
        )
        logger.info(f'sChain: {self.chain_name}. {self.node_id_dkg} node sent an alright note')

    def get_common_bls_public_key(self) -> list[str]:
        raw_common_public_key = self.skale.key_storage.get_common_public_key(self.group_index)
        return [elem for coord in raw_common_public_key for elem in coord]

    def is_broadcast_possible(self) -> bool:
        is_broadcast_possible = self.skale.dkg.contract.functions.isBroadcastPossible(
            self.group_index, self.node_id_contract
        ).call({'from': self.skale.wallet.address})

        channel_opened = self.is_channel_opened()
        if not is_broadcast_possible or not channel_opened:
            logger.info(
                f'sChain: {self.chain_name}. {self.node_id_dkg} node could not sent broadcast'
            )
            return False
        return True

    def is_alright_possible(self) -> bool:
        is_alright_possible = self.skale.dkg.is_alright_possible(
            self.group_index, self.node_id_contract, self.skale.wallet.address
        )

        if not is_alright_possible or not self.is_channel_opened():
            logger.info(
                f'sChain: {self.chain_name}. {self.node_id_dkg} node could not sent an alright note'
            )
            return False
        return True

    @sgx_unreachable_retry
    def generate_bls_key(self):
        received_secret_key_contribution = ''.join(
            to_verify(self.incoming_secret_key_contribution[j]) for j in range(self.sgx.n)
        )
        logger.info(
            f'sChain: {self.chain_name}. '
            f'DKGClient is going to create BLS private key with name {self.bls_name}'
        )
        bls_private_key = self.sgx.create_bls_private_key_v2(
            self.poly_name, self.bls_name, self.eth_key_name, received_secret_key_contribution
        )
        logger.info(
            f'sChain: {self.chain_name}. '
            'DKGClient is going to fetch BLS public key with name {self.bls_name}'
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
                f'sChain: {self.chain_name}. Received by {self.node_id_dkg} from {from_node}'
            )

    def broadcast(self):
        poly_success = self.generate_polynomial(self.poly_name)
        if poly_success == DkgPolyStatus.FAIL:
            raise SgxDkgPolynomGenerationError(
                f'sChain: {self.chain_name}. Sgx dkg polynom generation failed'
            )

        if not self.is_broadcast_possible():
            return

        self._send_broadcast_transaction()
        logger.info('Everything is sent from %d node', self.node_id_dkg)
        self.last_completed_step = DKGStep.BROADCAST
