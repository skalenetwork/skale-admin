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

import os
import sys
import binascii
import logging
import eth_utils

from tools.configs import NODE_DATA_PATH, SGX_CERTIFICATES_FOLDER
from sgx import SgxClient

sys.path.insert(0, NODE_DATA_PATH)

logger = logging.getLogger(__name__)


class DkgError(Exception):
    pass


class DkgTransactionError(DkgError):
    pass


class DkgVerificationError(DkgError):
    pass


class SgxDkgPolynomGenerationError(DkgError):
    pass


def convert_g2_point_to_hex(data):
    data_hexed = ''
    for coord in data:
        temp = hex(int(coord))[2:]
        while (len(temp) < 64):
            temp = '0' + temp
        data_hexed += temp
    return data_hexed


def convert_g2_points_to_hex(data):
    data_hexed = ""
    for point in data:
        data_hexed += convert_g2_point_to_hex(point)
    return data_hexed


class DKGClient:
    def __init__(self, node_id_dkg, node_id_contract, skale, t, n, schain_name, public_keys,
                 node_ids_dkg, node_ids_contract, eth_key_name):
        self.sgx = SgxClient(os.environ['SGX_SERVER_URL'], n=n, t=t,
                             path_to_cert=SGX_CERTIFICATES_FOLDER)
        self.schain_name = schain_name
        self.group_index = skale.web3.sha3(text=self.schain_name)
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
        logger.info(
            f'Schain: {self.schain_name}. Node id on chain is {self.node_id_dkg}; '
            f'Node id on contract is {self.node_id_contract}')

    def is_channel_opened(self):
        return self.dkg_contract_functions.isChannelOpened.call(self.group_index)

    def generate_polynomial(self, poly_name):
        self.poly_name = poly_name
        return self.sgx.generate_dkg_poly(poly_name)

    def verification_vector(self):
        verification_vector = self.sgx.get_verification_vector(self.poly_name)
        self.incoming_verification_vector[self.node_id_dkg] = verification_vector
        verification_vector_hexed = eth_utils.conversions.add_0x_prefix(
            convert_g2_points_to_hex(verification_vector)
        )
        return verification_vector_hexed

    def secret_key_contribution(self):
        self.sent_secret_key_contribution = self.sgx.get_secret_key_contribution(self.poly_name,
                                                                                 self.public_keys)
        self.incoming_secret_key_contribution[self.node_id_dkg] = self.sent_secret_key_contribution[
            self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192
        ]
        return self.sent_secret_key_contribution

    def broadcast(self, poly_name):
        is_broadcast_possible_function = self.dkg_contract_functions.isBroadcastPossible
        is_broadcast_possible = is_broadcast_possible_function.call(self.group_index,
                                                                    self.node_id_contract)
        if not is_broadcast_possible or not self.is_channel_opened():
            logger.info(f'Broadcast is already sent from {self.node_id_dkg} node')
            return
        poly_success = self.generate_polynomial(poly_name)
        if not poly_success:
            raise SgxDkgPolynomGenerationError(
                f'Schain: {self.schain_name}. Sgx dkg polynom generation failed'
            )

        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()
        receipt = self.skale.dkg.broadcast(self.group_index,
                                           self.node_id_contract,
                                           verification_vector,
                                           secret_key_contribution,
                                           wait_for=True)
        status = receipt["status"]
        if status != 1:
            receipt = self.skale.dkg.broadcast(self.group_index,
                                               self.node_id_contract,
                                               verification_vector,
                                               secret_key_contribution,
                                               wait_for=True)
            status = receipt["status"]
            if status != 1:
                raise DkgTransactionError(f'Schain: {self.schain_name}. '
                                          f'Broadcast transaction failed, see receipt',
                                          receipt)
        logger.info(f'Schain: {self.schain_name}. Everything is sent from {self.node_id_dkg} node')

    def receive_verification_vector(self, from_node, event):
        input_ = binascii.hexlify(event['args']['verificationVector']).decode()
        self.incoming_verification_vector[from_node] = input_

    def receive_secret_key_contribution(self, from_node, event):
        input_ = binascii.hexlify(event['args']['secretKeyContribution']).decode()
        self.incoming_secret_key_contribution[from_node] = input_[
            self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192
        ]

    def verification(self, from_node):
        return self.sgx.verify_secret_share(self.incoming_verification_vector[from_node],
                                            self.eth_key_name,
                                            self.incoming_secret_key_contribution[from_node],
                                            self.node_id_dkg)

    def send_complaint(self, to_node):
        is_complaint_possible_function = self.dkg_contract_functions.isComplaintPossible
        is_complaint_possible = is_complaint_possible_function.call(self.group_index,
                                                                    self.node_id_contract, to_node)
        if not is_complaint_possible or not self.is_channel_opened():
            logger.info(f'{self.node_id_dkg} node could not sent a complaint on {to_node} node')
            return
        self.skale.dkg.complaint(self.group_index,
                                 self.node_id_contract,
                                 self.node_ids_dkg[to_node],
                                 wait_for=True)
        logger.info(f'Schain: {self.schain_name}. '
                    f'{self.node_id_dkg} node sent a complaint on {to_node} node')

    def response(self, from_node_index):
        is_response_possible_function = self.dkg_contract_functions.isResponsePossible
        is_response_possible = is_response_possible_function.call(self.group_index,
                                                                  self.node_id_contract)
        if not is_response_possible or not self.is_channel_opened():
            logger.info(f'{from_node_index} node could not sent a response')
            return
        response = self.sgx.complaint_response(self.poly_name, from_node_index)
        share, dh_key = response['share'], response['dh_key']

        share = convert_g2_point_to_hex(share)

        receipt = self.skale.dkg.response(self.group_index,
                                          self.node_id_contract,
                                          dh_key,
                                          share,
                                          wait_for=True)
        status = receipt['status']
        if status != 1:
            receipt = self.skale.dkg.response(self.group_index,
                                              self.node_id_contract,
                                              dh_key,
                                              share,
                                              wait_for=True)
            status = receipt['status']
            if status != 1:
                raise DkgTransactionError(
                    f"Schain: {self.schain_name}. "
                    "Response transaction failed, see receipt", receipt)
        logger.info(f'Schain: {self.schain_name}. {from_node_index} node sent a response')

    def receive_from_node(self, from_node, event):
        self.receive_verification_vector(self.node_ids_contract[from_node], event)
        self.receive_secret_key_contribution(self.node_ids_contract[from_node], event)
        if not self.verification(self.node_ids_contract[from_node]):
            raise DkgVerificationError(
                f"Schain: {self.schain_name}. "
                f"Fatal error : user {str(self.node_ids_contract[from_node] + 1)} "
                f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
            )
        logger.info(f'Schain: {self.schain_name}. '
                    f'All data from {self.node_ids_contract[from_node]} was received and verified')

    def generate_key(self, bls_key_name):
        received_secret_key_contribution = "".join(self.incoming_secret_key_contribution[j]
                                                   for j in range(self.sgx.n))
        logger.info(f'Schain: {self.schain_name}. '
                    f'DKGClient is going to create BLS private key with name {bls_key_name}')
        bls_private_key = self.sgx.create_bls_private_key(self.poly_name, bls_key_name,
                                                          self.eth_key_name,
                                                          received_secret_key_contribution)
        logger.info(f'Schain: {self.schain_name}. '
                    'DKGClient is going to fetch BLS public key with name {bls_key_name}')
        self.public_key = self.sgx.get_bls_public_key(bls_key_name)
        return bls_private_key

    def allright(self):
        is_allright_possible_function = self.dkg_contract_functions.isAlrightPossible
        is_allright_possible = is_allright_possible_function.call(self.group_index,
                                                                  self.node_id_contract)
        if not is_allright_possible or not self.is_channel_opened():
            logger.info(f'{self.node_id_dkg} node has already sent an allright note')
            return
        receipt = self.skale.dkg.allright(self.group_index, self.node_id_contract,
                                          wait_for=True)
        status = receipt['status']
        if status != 1:
            receipt = self.skale.dkg.allright(self.group_index, self.node_id_contract,
                                              wait_for=True)
            status = receipt['status']
            if status != 1:
                raise DkgTransactionError(
                    f'Schain: {self.schain_name}. '
                    f'Allright transaction failed, see receipt', receipt
                )
        logger.info(f'Schain: {self.schain_name}. {self.node_id_dkg} node sent an allright note')
