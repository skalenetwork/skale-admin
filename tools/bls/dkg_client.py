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
import sys

from sgx import SgxClient
from sgx.http import SgxUnreachableError
from sgx.sgx_rpc_handler import DkgPolyStatus
from skale.contracts.manager.dkg import G2Point, KeyShare
from skale.transactions.result import TransactionFailedError

from tools.configs import NODE_DATA_PATH, SGX_CERTIFICATES_FOLDER
from tools.sgx_utils import sgx_unreachable_retry

sys.path.insert(0, NODE_DATA_PATH)

logger = logging.getLogger(__name__)

ALRIGHT_GAS_LIMIT = 1000000


class DkgError(Exception):
    pass


class DkgTransactionError(DkgError):
    pass


class DkgVerificationError(DkgError):
    pass


class SgxDkgPolynomGenerationError(DkgError):
    pass


def convert_g2_points_to_array(data):
    g2_array = []
    for point in data:
        new_point = []
        for coord in point:
            new_coord = int(coord)
            new_point.append(new_coord)
        g2_array.append(G2Point(*new_point).tuple)
    return g2_array


def convert_g2_array_to_hex(data):
    data_hexed = ''
    for point in data:
        data_hexed += convert_g2_point_to_hex(point)
    return data_hexed


def convert_g2_point_to_hex(data):
    data_hexed = ''
    for coord in data:
        temp = hex(int(coord))[2:]
        while (len(temp) < 64):
            temp = '0' + temp
        data_hexed += temp
    return data_hexed


def convert_hex_to_g2_array(data):
    g2_array = []
    while len(data) > 0:
        cur = data[:256]
        g2_array.append([str(x) for x in [int(cur[64 * i:64 * i + 64], 16) for i in range(4)]])
        data = data[256:]
    return g2_array


def convert_str_to_key_share(sent_secret_key_contribution, n):
    return_value = []
    for i in range(n):
        public_key = sent_secret_key_contribution[i * 192 + 64: (i + 1) * 192]
        key_share = bytes.fromhex(sent_secret_key_contribution[i * 192: i * 192 + 64])
        return_value.append(KeyShare(public_key, key_share).tuple)
    return return_value


def convert_key_share_to_str(data, n):
    return "".join(to_verify(s) for s in [data[i * 192:(i + 1) * 192] for i in range(n)])


def to_verify(share):
    return share[128:192] + share[:128]


def get_dkg_timeout(skale):
    return skale.constants_holder.contract.functions.complaintTimelimit().call()


class DKGClient:
    def __init__(self, node_id_dkg, node_id_contract, skale, t, n, schain_name, public_keys,
                 node_ids_dkg, node_ids_contract, eth_key_name):
        self.sgx = SgxClient(os.environ['SGX_SERVER_URL'], n=n, t=t,
                             path_to_cert=SGX_CERTIFICATES_FOLDER)
        self.schain_name = schain_name
        self.group_index = skale.schains.name_to_group_id(schain_name)
        self.node_id_contract = node_id_contract
        self.node_id_dkg = node_id_dkg
        self.skale = skale
        self.t = t
        self.n = n
        self.eth_key_name = eth_key_name
        self.incoming_verification_vector = ['0' for _ in range(n)]
        self.incoming_secret_key_contribution = ['0' for _ in range(n)]
        self.public_keys = public_keys
        self.node_ids_dkg = node_ids_dkg
        self.node_ids_contract = node_ids_contract
        self.dkg_contract_functions = self.skale.dkg.contract.functions
        self.dkg_timeout = get_dkg_timeout(self.skale)
        self.complaint_error_event_hash = self.skale.web3.toHex(self.skale.web3.sha3(
            text="ComplaintError(string)"
        ))
        logger.info(
            f'sChain: {self.schain_name}. Node id on chain is {self.node_id_dkg}; '
            f'Node id on contract is {self.node_id_contract}')
        logger.info(f'sChain: {self.schain_name}. DKG timeout is {self.dkg_timeout}')

    def is_channel_opened(self):
        return self.skale.dkg.is_channel_opened(self.group_index)

    def check_complaint_logs(self, logs):
        return logs['topics'][0].hex() != self.complaint_error_event_hash

    def store_broadcasted_data(self, data, from_node):
        self.incoming_secret_key_contribution[from_node] = data[1][
            192 * self.node_id_dkg: 192 * (self.node_id_dkg + 1)
        ]
        if from_node == self.node_id_dkg:
            self.incoming_verification_vector[from_node] = convert_hex_to_g2_array(data[0])
            self.sent_secret_key_contribution = convert_key_share_to_str(data[1], self.n)
        else:
            self.incoming_verification_vector[from_node] = data[0]

    @sgx_unreachable_retry
    def generate_polynomial(self, poly_name):
        self.poly_name = poly_name
        return self.sgx.generate_dkg_poly(poly_name)

    @sgx_unreachable_retry
    def verification_vector(self):
        verification_vector = self.sgx.get_verification_vector(self.poly_name)
        self.incoming_verification_vector[self.node_id_dkg] = verification_vector
        return convert_g2_points_to_array(verification_vector)

    @sgx_unreachable_retry
    def secret_key_contribution(self):
        self.sent_secret_key_contribution = self.sgx.get_secret_key_contribution_v2(self.poly_name,
                                                                                    self.public_keys
                                                                                    )
        self.incoming_secret_key_contribution[self.node_id_dkg] = self.sent_secret_key_contribution[
            self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192
        ]
        return convert_str_to_key_share(self.sent_secret_key_contribution, self.n)

    def broadcast(self, poly_name):
        poly_success = self.generate_polynomial(poly_name)
        if poly_success == DkgPolyStatus.FAIL:
            raise SgxDkgPolynomGenerationError(
                f'sChain: {self.schain_name}. Sgx dkg polynom generation failed'
            )

        is_broadcast_possible = self.skale.dkg.is_broadcast_possible(
            self.group_index, self.node_id_contract, self.skale.wallet.address
        )

        channel_opened = self.is_channel_opened()
        if not is_broadcast_possible or not channel_opened:
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent broadcast')
            return

        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()

        try:
            self.skale.dkg.broadcast(
                self.group_index,
                self.node_id_contract,
                verification_vector,
                secret_key_contribution,
            )
        except TransactionFailedError as e:
            logger.error(f'DKG broadcast failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. Everything is sent from {self.node_id_dkg} node')

    def receive_from_node(self, from_node, broadcasted_data):
        self.store_broadcasted_data(broadcasted_data, from_node)
        if from_node == self.node_id_dkg:
            return

        try:
            if not self.verification(from_node):
                raise DkgVerificationError(
                    f"sChain: {self.schain_name}. "
                    f"Fatal error : user {str(from_node + 1)} "
                    f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                )
            logger.info(f'sChain: {self.schain_name}. '
                        f'All data from {from_node} was received and verified')
        except SgxUnreachableError as e:
            raise SgxUnreachableError(
                    f"sChain: {self.schain_name}. "
                    f"Fatal error : user {str(from_node + 1)} "
                    f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
                    f"with SgxUnreachableError: ", e
                )

    @sgx_unreachable_retry
    def verification(self, from_node):
        return self.sgx.verify_secret_share_v2(self.incoming_verification_vector[from_node],
                                               self.eth_key_name,
                                               to_verify(
                                                self.incoming_secret_key_contribution[from_node]
                                               ),
                                               self.node_id_dkg)

    @sgx_unreachable_retry
    def generate_bls_key(self, bls_key_name):
        received_secret_key_contribution = "".join(to_verify(
                                                    self.incoming_secret_key_contribution[j]
                                                    )
                                                   for j in range(self.sgx.n))
        logger.info(f'sChain: {self.schain_name}. '
                    f'DKGClient is going to create BLS private key with name {bls_key_name}')
        bls_private_key = self.sgx.create_bls_private_key_v2(self.poly_name, bls_key_name,
                                                             self.eth_key_name,
                                                             received_secret_key_contribution)
        logger.info(f'sChain: {self.schain_name}. '
                    'DKGClient is going to fetch BLS public key with name {bls_key_name}')
        self.public_key = self.sgx.get_bls_public_key(bls_key_name)
        return bls_private_key

    def get_bls_public_keys(self):
        self.incoming_verification_vector[self.node_id_dkg] = convert_g2_array_to_hex(
            self.incoming_verification_vector[self.node_id_dkg]
        )
        return self.sgx.calculate_all_bls_public_keys(self.incoming_verification_vector)

    def alright(self):
        is_alright_possible = self.skale.dkg.is_alright_possible(
            self.group_index, self.node_id_contract, self.skale.wallet.address)

        if not is_alright_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent an alright note')
            return
        try:
            self.skale.dkg.alright(
                self.group_index,
                self.node_id_contract,
                gas_limit=ALRIGHT_GAS_LIMIT
            )
        except TransactionFailedError as e:
            logger.error(f'DKG alright failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. {self.node_id_dkg} node sent an alright note')

    def send_complaint(self, to_node, report_bad_data=False):
        reason = "complaint"
        if report_bad_data:
            reason = "complaint_bad_data"
        logger.info(f'sChain: {self.schain_name}. '
                    f'{self.node_id_dkg} is trying to sent a {reason} on {to_node} node')

        is_complaint_possible = self.skale.dkg.is_complaint_possible(
            self.group_index, self.node_id_contract, self.node_ids_dkg[to_node],
            self.skale.wallet.address
        )

        if not is_complaint_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent a complaint on {to_node} node')
            return False
        try:
            if not report_bad_data:
                tx_res = self.skale.dkg.complaint(
                    self.group_index,
                    self.node_id_contract,
                    self.node_ids_dkg[to_node],
                    wait_for=True
                )
            else:
                tx_res = self.skale.dkg.complaint_bad_data(
                    self.group_index,
                    self.node_id_contract,
                    self.node_ids_dkg[to_node],
                    wait_for=True
                )
            if self.check_complaint_logs(tx_res.receipt['logs'][0]):
                logger.info(f'sChain: {self.schain_name}. '
                            f'{self.node_id_dkg} node sent a complaint on {to_node} node')
                return True
            else:
                logger.info(f'sChain: {self.schain_name}. Complaint from {self.node_id_dkg} on '
                            f'{to_node} node was rejected')
                return False
        except TransactionFailedError as e:
            logger.error(f'DKG complaint failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)

    @sgx_unreachable_retry
    def get_complaint_response(self, to_node_index):
        response = self.sgx.complaint_response(
            self.poly_name,
            self.node_ids_contract[to_node_index]
        )
        share, dh_key = response['share'], response['dh_key']
        verification_vector_mult = response['verification_vector_mult']
        share = share.split(':')
        for i in range(4):
            share[i] = int(share[i])
        share = G2Point(*share).tuple
        return share, dh_key, verification_vector_mult

    def response(self, to_node_index):
        is_pre_response_possible = self.skale.dkg.is_pre_response_possible(
            self.group_index, self.node_id_contract, self.skale.wallet.address)

        if not is_pre_response_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent a response')
            return

        share, dh_key, verification_vector_mult = self.get_complaint_response(to_node_index)

        try:
            self.skale.dkg.pre_response(
                self.group_index,
                self.node_id_contract,
                convert_g2_points_to_array(self.incoming_verification_vector[self.node_id_dkg]),
                convert_g2_points_to_array(verification_vector_mult),
                convert_str_to_key_share(self.sent_secret_key_contribution, self.n),
                wait_for=True
            )

            is_response_possible = self.skale.dkg.is_response_possible(
                self.group_index, self.node_id_contract, self.skale.wallet.address)

            if not is_response_possible or not self.is_channel_opened():
                logger.info(f'sChain: {self.schain_name}. '
                            f'{self.node_id_dkg} node could not sent a response')
                return

            self.skale.dkg.response(
                self.group_index,
                self.node_id_contract,
                int(dh_key, 16),
                share,
                wait_for=True
            )
            logger.info(f'sChain: {self.schain_name}. {self.node_id_dkg} node sent a response')
        except TransactionFailedError as e:
            logger.error(f'DKG response failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)

    def is_all_data_received(self, from_node):
        return self.skale.dkg.is_all_data_received(self.group_index, self.node_ids_dkg[from_node])

    def is_everyone_broadcasted(self):
        return self.skale.dkg.is_everyone_broadcasted(self.group_index, self.skale.wallet.address)

    def is_everyone_sent_algright(self):
        return self.skale.dkg.get_number_of_completed(self.group_index) == self.n
