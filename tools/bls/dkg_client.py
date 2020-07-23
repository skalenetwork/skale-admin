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

from skale.transactions.result import TransactionFailedError
from tools.configs import NODE_DATA_PATH, SGX_CERTIFICATES_FOLDER
from sgx import SgxClient
from sgx.sgx_rpc_handler import DkgPolyStatus

from skale.contracts.dkg import G2Point, KeyShare

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


def convert_g2_points_to_array(data):
    g2_array = []
    for point in data:
        new_point = []
        for coord in point:
            new_coord = int(coord)
            new_point.append(new_coord)
        g2_array.append(G2Point(*new_point).tuple)
    return g2_array


def convert_g2_point_to_hex(data):
    data_hexed = ''
    for coord in data:
        temp = hex(int(coord))[2:]
        while (len(temp) < 64):
            temp = '0' + temp
        data_hexed += temp
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
        return convert_g2_points_to_array(verification_vector)

    def secret_key_contribution(self):
        sent_secret_key_contribution = self.sgx.get_secret_key_contribution(self.poly_name,
                                                                            self.public_keys)
        self.incoming_secret_key_contribution[self.node_id_dkg] = sent_secret_key_contribution[
            self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192
        ]
        return_value = []
        for i in range(self.n):
            public_key = sent_secret_key_contribution[i * 192: i * 192 + 128]
            key_share = bytes.fromhex(sent_secret_key_contribution[i * 192 + 128: (i + 1) * 192])
            return_value.append(KeyShare(public_key, key_share).tuple)
        return return_value

    def broadcast(self, poly_name):
        poly_success = self.generate_polynomial(poly_name)
        if poly_success == DkgPolyStatus.FAIL:
            raise SgxDkgPolynomGenerationError(
                f'sChain: {self.schain_name}. Sgx dkg polynom generation failed'
            )

        if poly_success == DkgPolyStatus.PREEXISTING:
            secret_key_contribution, verification_vector = self.get_broadcasted_data(
                self.node_id_dkg
            )
            self.receive_secret_key_contribution(self.node_id_dkg, secret_key_contribution)
            self.receive_verification_vector(self.node_id_dkg, verification_vector)

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
            self.skale.dkg.broadcast(
                self.group_index,
                self.node_id_contract,
                verification_vector,
                secret_key_contribution,
                gas_price=self.skale.dkg.gas_price()
            )
        except TransactionFailedError as e:
            logger.error(f'DKG broadcast failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. Everything is sent from {self.node_id_dkg} node')

    def receive_verification_vector(self, from_node, broadcasted_data):
        hexed_vv = ""
        for point in broadcasted_data:
            hexed_vv += convert_g2_point_to_hex([*point[0], *point[1]])
        self.incoming_verification_vector[from_node] = hexed_vv

    def receive_secret_key_contribution(self, from_node, broadcasted_data):
        public_key_x_str = binascii.hexlify(broadcasted_data[self.node_id_dkg][0][0]).decode()
        public_key_y_str = binascii.hexlify(broadcasted_data[self.node_id_dkg][0][1]).decode()
        key_share_str = binascii.hexlify(broadcasted_data[self.node_id_dkg][1]).decode()
        incoming = public_key_x_str + public_key_y_str + key_share_str
        self.incoming_secret_key_contribution[from_node] = incoming

    def verification(self, from_node):
        return self.sgx.verify_secret_share(self.incoming_verification_vector[from_node],
                                            self.eth_key_name,
                                            self.incoming_secret_key_contribution[from_node],
                                            self.node_id_dkg)

    def send_complaint(self, to_node):
        logger.info(f'sChain: {self.schain_name}. '
                    f'{self.node_id_dkg} is trying to sent a complaint on {to_node} node')
        is_complaint_possible_function = self.dkg_contract_functions.isComplaintPossible
        is_complaint_possible = is_complaint_possible_function(
            self.group_index, self.node_id_contract, self.node_ids_dkg[to_node]).call(
                {'from': self.skale.wallet.address})

        if not is_complaint_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent a complaint on {to_node} node')
            return
        try:
            self.skale.dkg.complaint(
                self.group_index,
                self.node_id_contract,
                self.node_ids_dkg[to_node],
                gas_price=self.skale.dkg.gas_price(),
                wait_for=True
            )
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node sent a complaint on {to_node} node')
        except TransactionFailedError as e:
            logger.error(f'DKG complaint failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)

    def response(self, to_node_index):
        is_response_possible_function = self.dkg_contract_functions.isResponsePossible
        is_response_possible = is_response_possible_function(
            self.group_index, self.node_id_contract).call({'from': self.skale.wallet.address})

        if not is_response_possible or not self.is_channel_opened():
            logger.info(f'sChain: {self.schain_name}. '
                        f'{self.node_id_dkg} node could not sent a response')
            return
        response = self.sgx.complaint_response(
            self.poly_name,
            self.node_ids_contract[to_node_index]
        )
        share, dh_key = response['share'], response['dh_key']

        share = share.split(':')
        for i in range(4):
            share[i] = int(share[i])
        share = G2Point(*share).tuple
        try:
            self.skale.dkg.response(
                self.group_index,
                self.node_id_contract,
                int(dh_key, 16),
                share,
                gas_price=self.skale.dkg.gas_price()
            )
        except TransactionFailedError as e:
            logger.error(f'DKG response failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. {self.node_id_dkg} node sent a response')

    def get_broadcasted_data(self, from_node):
        return self.skale.key_storage.get_broadcasted_data(
            self.group_index, self.node_ids_dkg[from_node]
        )

    def is_all_data_received(self, from_node):
        is_all_data_received_function = self.dkg_contract_functions.isAllDataReceived
        return is_all_data_received_function(self.group_index, self.node_ids_dkg[from_node]).call(
            {'from': self.skale.wallet.address}
        )

    def is_everyone_broadcasted(self):
        get_number_of_broadcasted_function = self.dkg_contract_functions.isEveryoneBroadcasted
        return get_number_of_broadcasted_function(self.group_index).call(
            {'from': self.skale.wallet.address}
        )

    def get_channel_started_time(self):
        get_channel_started_time_function = self.dkg_contract_functions.getChannelStartedTime
        return get_channel_started_time_function(self.group_index).call(
            {'from': self.skale.wallet.address}
        )

    def get_complaint_started_time(self):
        get_complaint_started_time_function = self.dkg_contract_functions.getComplaintStartedTime
        return get_complaint_started_time_function(self.group_index).call(
            {'from': self.skale.wallet.address}
        )
    
    def get_alright_started_time(self):
        get_alright_started_time_function = self.dkg_contract_functions.getAlrightStartedTime
        return get_alright_started_time_function(self.group_index).call(
            {'from': self.skale.wallet.address}
        )

    def get_complaint_data(self):
        get_complaint_data_function = self.dkg_contract_functions.getComplaintData
        return get_complaint_data_function(self.group_index).call(
            {'from': self.skale.wallet.address}
        )

    def receive_from_node(self, from_node, broadcasted_data):
        self.receive_verification_vector(from_node, broadcasted_data[0])
        self.receive_secret_key_contribution(from_node, broadcasted_data[1])
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
            self.skale.dkg.alright(
                self.group_index,
                self.node_id_contract,
                gas_price=self.skale.dkg.gas_price()
            )
        except TransactionFailedError as e:
            logger.error(f'DKG alright failed: sChain {self.schain_name}')
            raise DkgTransactionError(e)
        logger.info(f'sChain: {self.schain_name}. {self.node_id_dkg} node sent an alright note')
