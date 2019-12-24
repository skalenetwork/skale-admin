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

from skale.utils.web3_utils import wait_receipt

from tools.configs import NODE_DATA_PATH
from sgx import SgxClient

sys.path.insert(0, NODE_DATA_PATH)

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)


class DkgVerificationError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class SgxDkgPolynomGenerationError(Exception):
    def __init__(self, msg):
        super().__init__(msg)


def convert_g2_point_to_hex(data):
    data_hexed = ""
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
        self.sgx = SgxClient(os.environ['SGX_SERVER_URL'], n=n, t=t)
        self.schain_name = schain_name
        self.group_index = skale.web3.sha3(text=self.schain_name)
        self.node_id_contract = node_id_contract
        self.node_id_dkg = node_id_dkg
        self.skale = skale
        self.t = t
        self.n = n
        self.eth_key_name = eth_key_name
        self.incoming_verification_vector = ['0'] * n
        self.incoming_secret_key_contribution = ['0'] * n
        self.public_keys = public_keys
        self.node_ids_dkg = node_ids_dkg
        self.node_ids_contract = node_ids_contract
        logger.info(f'Node id on chain is {self.node_id_dkg}; \
            Node id on contract is {self.node_id_contract}')

    def GeneratePolynomial(self, poly_name):
        self.poly_name = poly_name
        return self.sgx.generate_dkg_poly(poly_name)

    def VerificationVector(self):
        verification_vector = self.sgx.get_verification_vector(self.poly_name)
        self.incoming_verification_vector[self.node_id_dkg] = verification_vector
        verification_vector_hexed = eth_utils.conversions.add_0x_prefix(convert_g2_points_to_hex(verification_vector))
        return verification_vector_hexed

    def SecretKeyContribution(self):
        self.sent_secret_key_contribution = self.sgx.get_secret_key_contribution(self.poly_name, self.public_keys)
        self.incoming_secret_key_contribution[self.node_id_dkg] = self.sent_secret_key_contribution[self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192]
        return self.sent_secret_key_contribution

    def Broadcast(self, poly_name):
        poly_success = self.GeneratePolynomial(poly_name)
        if not poly_success:
            raise SgxDkgPolynomGenerationError("SGX DKG POLYNOM GENERATION FAILED")

        verification_vector = self.VerificationVector()
        secret_key_contribution = self.SecretKeyContribution()
        res = self.skale.dkg.broadcast(self.group_index,
                                       self.node_id_contract,
                                       verification_vector,
                                       secret_key_contribution)
        receipt = wait_receipt(self.skale.web3, res, timeout=20)
        status = receipt["status"]
        if status != 1:
            res = self.skale.dkg.broadcast(self.group_index,
                                           self.node_id_contract,
                                           verification_vector,
                                           secret_key_contribution)
            receipt = wait_receipt(self.skale.web3, res, timeout=20)
            status = receipt["status"]
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'Everything is sent from {self.node_id_dkg} node')

    def RecieveVerificationVector(self, fromNode, event):
        input_ = binascii.hexlify(event['args']['verificationVector']).decode()
        self.incoming_verification_vector[fromNode] = input_

    def RecieveSecretKeyContribution(self, fromNode, event):
        input_ = binascii.hexlify(event['args']['secretKeyContribution']).decode()
        self.incoming_secret_key_contribution[fromNode] = input_[self.node_id_dkg * 192: (self.node_id_dkg + 1) * 192]

    def Verification(self, fromNode):
        return self.sgx.verify_secret_share(self.incoming_verification_vector[fromNode], self.eth_key_name, self.incoming_secret_key_contribution[fromNode], self.node_id_dkg)

    def SendComplaint(self, toNode):
        res = self.skale.dkg.complaint(self.group_index, self.node_id_contract, self.node_ids_dkg[toNode])
        wait_receipt(self.skale.web3, res, timeout=20)
        logger.info(f'{self.node_id_dkg} node sent a complaint on {toNode} node')

    def Response(self, from_node_index):
        response = self.sgx.complaint_response(self.poly_name, from_node_index)
        share, dh_key = response['share'], response['dh_key']

        share = convert_g2_point_to_hex(share)

        res = self.skale.dkg.response(self.group_index,
                                      self.node_id_contract,
                                      dh_key,
                                      share)
        receipt = wait_receipt(self.skale.web3, res, timeout=20)
        status = receipt['status']
        if status != 1:
            res = self.skale.dkg.response(self.group_index,
                                    self.node_id_contract,
                                    dh_key,
                                    share)
            receipt = wait_receipt(self.skale.web3, res, timeout=20)
            status = receipt['status']
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'{from_node_index} node sent a response')

    def RecieveFromNode(self, fromNode, event):
        self.RecieveVerificationVector(self.node_ids_contract[fromNode], event)
        self.RecieveSecretKeyContribution(self.node_ids_contract[fromNode], event)
        if not self.Verification(self.node_ids_contract[fromNode]):
            raise DkgVerificationError("Fatal error : user " + str(self.node_ids_contract[fromNode] + 1) + " hasn't passed verification by user " + str(self.node_id_dkg + 1))
        logger.info(f'All data from {self.node_ids_contract[fromNode]} was recieved and verified')

    def GenerateKey(self, bls_key_name):
        recieved_secret_key_contribution = "".join(self.incoming_secret_key_contribution[j] for j in range(self.sgx.n))
        logger.info(f'DKGClient is going to create BLS private key with name {bls_key_name}')
        bls_private_key = self.sgx.create_bls_private_key(self.poly_name, bls_key_name, self.eth_key_name, recieved_secret_key_contribution)
        logger.info(f'DKGClient is going to fetch BLS public key with name {bls_key_name}')
        self.public_key = self.sgx.get_bls_public_key(bls_key_name)
        return bls_private_key

    def Allright(self):
        res = self.skale.dkg.allright(self.group_index, self.node_id_contract)
        receipt = wait_receipt(self.skale.web3, res, timeout=20)
        status = receipt['status']
        if status != 1:
            res = self.skale.dkg.allright(self.group_index, self.node_id_contract)
            receipt = wait_receipt(self.skale.web3, res, timeout=20)
            status = receipt['status']
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'{self.node_id_dkg} node sent an allright note')
