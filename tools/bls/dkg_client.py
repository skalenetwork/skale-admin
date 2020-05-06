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

from skale.dataclasses.tx_res import TransactionFailedError
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
            f'sChain: {self.schain_name}. Node id on chain is {self.node_id_dkg}; '
            f'Node id on contract is {self.node_id_contract}')

    def is_channel_opened(self):
        return self.dkg_contract_functions.isChannelOpened(self.group_index).call()

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
        poly_success = self.generate_polynomial(poly_name)
        if not poly_success:
            raise SgxDkgPolynomGenerationError(
                f'sChain: {self.schain_name}. Sgx dkg polynom generation failed'
            )

        is_broadcast_possible_function = self.dkg_contract_functions.isBroadcastPossible
        is_broadcast_possible = is_broadcast_possible_function(
            self.group_index, self.node_id_contract).call({'from': self.skale.wallet.address})

        channel_opened = self.is_channel_opened()
        if not is_broadcast_possible or not channel_opened:
            logger.info(f'sChain: {self.schain_name}. '
                        f'Broadcast is already sent from {self.node_id_dkg} node')
            return

        verification_vector = self.verification_vector()
        secret_key_contribution = self.secret_key_contribution()
        try:
            tx_res = self.skale.dkg.broadcast(
                self.group_index,
                self.node_id_contract,
                verification_vector,
                secret_key_contribution,
                gas_price=self.skale.dkg.gas_price(),
                wait_for=True,
                retries=2
            )
            tx_res.raise_for_status()
        except TransactionFailedError as e:
            logger.error(f'DKG broadcast failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. Everything is sent from {self.node_id_dkg} node')

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
        is_complaint_possible = is_complaint_possible_function(
            self.group_index, self.node_id_contract, self.node_ids_dkg[to_node]).call(
                {'from': self.skale.wallet.address})

        if not is_complaint_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent a complaint on {to_node} node')
            return
        self.skale.dkg.complaint(self.group_index,
                                 self.node_id_contract,
                                 self.node_ids_dkg[to_node],
                                 gas_price=self.skale.dkg.gas_price(),
                                 wait_for=True)
        logger.info(f'sChain: {self.schain_name}. '
                    f'{self.node_id_dkg} node sent a complaint on {to_node} node')

    def response(self, from_node_index):
        is_response_possible_function = self.dkg_contract_functions.isResponsePossible
        is_response_possible = is_response_possible_function(
            self.group_index, self.node_id_contract).call({'from': self.skale.wallet.address})

        if not is_response_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{from_node_index} node could not sent a response')
            return
        response = self.sgx.complaint_response(
            self.poly_name,
            self.node_ids_contract[from_node_index]
        )
        share, dh_key = response['share'], response['dh_key']

        share = share.split(':')

        share = convert_g2_point_to_hex(share)
        try:
            tx_res = self.skale.dkg.response(
                self.group_index,
                self.node_id_contract,
                int(dh_key, 16),
                eth_utils.conversions.add_0x_prefix(share),
                gas_price=self.skale.dkg.gas_price(),
                wait_for=True,
                retries=2
            )
            tx_res.raise_for_status()
        except TransactionFailedError as e:
            logger.error(f'DKG response failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. {from_node_index} node sent a response')

    def get_broadcasted_data(self, from_node):
        get_broadcasted_data_function = self.dkg_contract_functions.getBroadcastedData
        return get_broadcasted_data_function(self.group_index, self.node_ids_dkg[from_node])

    def is_all_data_received(self, from_node):
        is_all_data_received_function = self.dkg_contract_functions.isAllDataReceived
        return is_all_data_received_function(self.group_index, from_node)

    def is_group_failed_dkg(self):
        is_group_failed_dkg_function = self.dkg_contract_functions.isGroupFailedDKG
        return is_group_failed_dkg_function(self.group_index)

    def get_complaint_data(self):
        get_complaint_data_function = self.dkg_contract_functions.getComplaintData
        return get_complaint_data_function(self.group_index)

    def receive_from_node(self, from_node, event):
        self.receive_verification_vector(from_node, event)
        self.receive_secret_key_contribution(from_node, event)
        if not self.verification(from_node):
            raise DkgVerificationError(
                f"sChain: {self.schain_name}. "
                f"Fatal error : user {str(from_node + 1)} "
                f"hasn't passed verification by user {str(self.node_id_dkg + 1)}"
            )
        logger.info(f'sChain: {self.schain_name}. '
                    f'All data from {from_node} was received and verified')

    def generate_key(self, bls_key_name):
        received_secret_key_contribution = "".join(self.incoming_secret_key_contribution[j]
                                                   for j in range(self.sgx.n))
        logger.info(f'sChain: {self.schain_name}. '
                    f'DKGClient is going to create BLS private key with name {bls_key_name}')
        bls_private_key = self.sgx.create_bls_private_key(self.poly_name, bls_key_name,
                                                          self.eth_key_name,
                                                          received_secret_key_contribution)
        logger.info(f'sChain: {self.schain_name}. '
                    'DKGClient is going to fetch BLS public key with name {bls_key_name}')
        self.public_key = self.sgx.get_bls_public_key(bls_key_name)
        return bls_private_key

    def alright(self):
        is_alright_possible_function = self.dkg_contract_functions.isAlrightPossible
        is_alright_possible = is_alright_possible_function(
            self.group_index, self.node_id_contract).call({'from': self.skale.wallet.address})

        if not is_alright_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node has already sent an alright note')
            return
        try:
            tx_res = self.skale.dkg.alright(
                self.group_index,
                self.node_id_contract,
                gas_price=self.skale.dkg.gas_price(),
                wait_for=True,
                retries=2
            )
            tx_res.raise_for_status()
        except TransactionFailedError as e:
            logger.error(f'DKG alright failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. {self.node_id_dkg} node sent an alright note')
