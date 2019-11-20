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

import sys
import binascii
import logging
import coincurve

from time import sleep
from tools.configs import NODE_DATA_PATH

sys.path.insert(0, NODE_DATA_PATH)
from dkgpython import dkg
from skale.utils.web3_utils import wait_receipt

logger = logging.getLogger(__name__)

def bxor(b1, b2):
    parts = []
    for b1, b2 in zip(b1, b2):
        parts.append(bytes([b1 ^ b2]))
    return b''.join(parts)

def encrypt(plaintext, secret_key):
    plaintext_in_bytes = bytearray(int(plaintext).to_bytes(32, byteorder ='big'))
    return bxor(plaintext_in_bytes, secret_key)

def decrypt(ciphertext, secret_key):
    xor_val = bxor(ciphertext, secret_key)
    ret_val = binascii.hexlify(xor_val)
    return str(int(ret_val.decode(), 16))

class DkgVerificationError(Exception):
    def __init__(self, msg):
        super().__init__(msg)

def convert_g2_points_to_hex(data):
    data_hexed = "0x"
    for coord in data:
        for elem in coord:
            temp = hex(int(elem[0]))[2:]
            while (len(temp) < 64):
                temp = '0' + temp
            data_hexed += temp
            temp = hex(int(elem[1]))[2:]
            while len(temp) < 64 :
                temp = '0' + temp
            data_hexed += temp
    return data_hexed

def convert_g2_point_to_hex(data):
    data_hexed = "0x"
    for coord in data:
        for elem in coord:
            temp = hex(int(elem[0]))[2:]
            while (len(temp) < 64):
                temp = '0' + temp
            data_hexed += temp
    return data_hexed

class DKGClient:
    def __init__(self, node_id_dkg, node_id_contract, node_web3, skale, wallet, t, n, schain_name, public_keys, node_ids_dkg, node_ids_contract):
        self.schain_name = schain_name
        self.group_index = node_web3.sha3(text = self.schain_name)
        self.node_id_contract = node_id_contract
        self.node_id_dkg = node_id_dkg
        self.node_web3 = node_web3
        self.skale = skale
        self.wallet = wallet
        self.t = t
        self.n = n
        self.dkg_instance = dkg(t, n)
        self.incoming_verification_vector = ['0'] * n
        self.incoming_secret_key_contribution = ['0'] * n
        self.public_keys = public_keys
        self.node_ids_dkg = node_ids_dkg
        self.node_ids_contract = node_ids_contract
        self.disposable_keys = ['0'] * n
        self.ecdh_keys = ['0'] * n
        logger.info(f'Node id on chain is {self.node_id_dkg} + "\n" Node id on contract is {self.node_id_contract}')

    def GeneratePolynomial(self):
        return self.dkg_instance.GeneratePolynomial()

    def VerificationVector(self, polynom):
        verification_vector = self.dkg_instance.VerificationVector(polynom)
        self.incoming_verification_vector[self.node_id_dkg] = verification_vector
        verification_vector_hexed = convert_g2_points_to_hex(verification_vector)
        return verification_vector_hexed

    def SecretKeyContribution(self, polynom):
        self.sent_secret_key_contribution = self.dkg_instance.SecretKeyContribution(polynom)
        secret_key_contribution = self.sent_secret_key_contribution
        self.incoming_secret_key_contribution[self.node_id_dkg] = secret_key_contribution[self.node_id_dkg]
        to_broadcast = bytes('', 'utf-8')
        for i in range(self.n):
            self.disposable_keys[i] = coincurve.keys.PrivateKey(coincurve.utils.get_valid_secret())
            self.ecdh_keys[i] = self.public_keys[i].multiply(self.disposable_keys[i].secret).format(compressed=False)[1:33]
            secret_key_contribution[i] = encrypt(secret_key_contribution[i], self.ecdh_keys[i])
            while len(secret_key_contribution[i]) < 32:
                secret_key_contribution[i] = bytes('0', 'utf-8') + secret_key_contribution[i]
            to_broadcast = to_broadcast + secret_key_contribution[i] + self.disposable_keys[i].public_key.format(compressed=False)
        return to_broadcast

    def Broadcast(self):
        polynom = self.GeneratePolynomial()
        verification_vector = self.VerificationVector(polynom)
        secret_key_contribution = self.SecretKeyContribution(polynom)
        res = self.skale.dkg.broadcast(self.group_index,
                                       self.node_id_contract,
                                       verification_vector,
                                       secret_key_contribution)
        receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
        status = receipt["status"]
        if status != 1:
            res = self.skale.dkg.broadcast(self.group_index,
                                           self.node_id_contract,
                                           verification_vector,
                                           secret_key_contribution)
            receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
            status = receipt["status"]
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'Everything is sent from {self.node_id_dkg} node')

    def RecieveVerificationVector(self, fromNode, event):
        input = binascii.hexlify(event['args']['verificationVector'])
        incoming_verification_vector = []
        while len(input) > 0 :
            cur = input[:64]
            input = input[64:]
            while cur[0] == '0':
                cur = cur[1:]
            incoming_verification_vector.append(str(int(cur, 16)))
        to_verify = []
        while len(incoming_verification_vector) > 0:
            smth = []
            smth.append((incoming_verification_vector[0], incoming_verification_vector[1]))
            smth.append((incoming_verification_vector[2], incoming_verification_vector[3]))
            to_verify.append(smth)
            incoming_verification_vector = incoming_verification_vector[4:]
        self.incoming_verification_vector[fromNode] = to_verify

    def RecieveSecretKeyContribution(self, fromNode, event):
        input = event['args']['secretKeyContribution']
        incoming_secret_key_contribution = []
        sent_public_keys = []
        while len(input) > 0:
            cur = input[:97]
            input = input[97:]
            sent_public_keys.append(cur[-65:])
            cur = cur[:-65]
            incoming_secret_key_contribution.append(cur)
        ecdh_key = coincurve.PublicKey(sent_public_keys[self.node_id_dkg]).multiply(coincurve.keys.PrivateKey.from_hex(self.wallet["private_key"][2:]).secret).format(compressed=False)[1:33]
        incoming_secret_key_contribution[self.node_id_dkg] = decrypt(incoming_secret_key_contribution[self.node_id_dkg], ecdh_key)
        self.incoming_secret_key_contribution[fromNode] = incoming_secret_key_contribution[self.node_id_dkg]

    def Verification(self, fromNode):
        return self.dkg_instance.Verification(self.node_id_dkg, self.incoming_secret_key_contribution[fromNode], self.incoming_verification_vector[fromNode])

    def SecretKeyShareCreate(self):
        self.secret_key_share = self.dkg_instance.SecretKeyShareCreate(self.incoming_secret_key_contribution)
        self.public_key = self.dkg_instance.GetPublicKeyFromSecretKey(self.secret_key_share)

    def SendComplaint(self, toNode):
        res = self.skale.dkg.complaint(self.group_index, self.node_id_contract, self.node_ids_dkg[toNode])
        wait_receipt(self.node_web3, res.hex(), timeout=20)
        logger.info(f'{self.node_id_dkg} node sent a complaint on {toNode} node')

    def Response(self):
        value_to_send = convert_g2_point_to_hex(
            self.dkg_instance.ComputeVerificationValue(
                decrypt(
                    self.sent_secret_key_contribution[fromNodeIndex][:32],
                    self.ecdh_keys[fromNodeIndex]
                )
            )
        )
        res = self.skale.dkg.response(self.group_index,
                                      self.node_id_contract,
                                      self.disposable_keys[self.node_id_dkg].to_int(),
                                      value_to_send)
        receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
        status = receipt['status']
        if status != 1:
            res = self.skale.dkg.response(
                self.group_index,
                self.node_ids[fromNodeIndex],
                self.disposable_keys[self.node_ids[fromNodeIndex]].to_int(),
                value_to_send)
            receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
            status = receipt['status']
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'{fromNodeIndex} node sent a response')

    def RecieveAll(self, fromNode, event):
        self.RecieveVerificationVector(self.node_ids_contract[fromNode], event)
        self.RecieveSecretKeyContribution(self.node_ids_contract[fromNode], event)
        if not self.Verification(self.node_ids_contract[fromNode]):
            raise DkgVerificationError("Fatal error : user " + str(self.node_ids_contract[fromNode] + 1) + " hasn't passed verification by user " + str(self.node_id_dkg + 1))
        self.SecretKeyShareCreate()
        logger.info("All data was recieved and verified, secret key share was generated")

    def Allright(self):
        res = self.skale.dkg.allright(self.group_index, self.node_id_contract)
        receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
        status = receipt['status']
        if status != 1:
            res = self.skale.dkg.allright(self.group_index, self.node_id_contract)
            receipt = wait_receipt(self.node_web3, res.hex(), timeout=20)
            status = receipt['status']
            if status != 1:
                raise ValueError("Transaction failed, see receipt", receipt)
        logger.info(f'{self.node_id_dkg} node sent an allright note')
