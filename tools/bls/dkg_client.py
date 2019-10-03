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
import json
import logging
import secrets
import coincurve

print(sys.path)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dkgpython
from dkgpython import dkg

from skale.utils.helper import await_receipt

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
    ret_val = ciphertext ^ secret_key
    return str.decode(ret_val)

class DkgVerificationError(Exception):
	pass


def sign_and_send(web3, method, gas_amount, wallet):
    eth_nonce = web3.eth.getTransactionCount(wallet['address'])
    txn = method.buildTransaction({
        'gas': gas_amount,
        'nonce': eth_nonce
    })
    signed_txn = web3.eth.account.signTransaction(txn, private_key=wallet['private_key'])
    tx = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
    logger.info(f'{method.__class__.__name__} - transaction_hash: {web3.toHex(tx)}')
    return tx

class DKGClient:
    def __init__(self, node_id, node_web3, wallet, t, n, schain_name, public_keys):
        print("Node id is", node_id)
        self.node_id = node_id
        self.node_web3 = node_web3
        self.wallet = wallet
        self.t = t
        self.n = n
        self.schain_name = schain_name
        self.group_index = node_web3.sha3(text = self.schain_name)
        self.public_keys = public_keys
        self.disposable_keys = ['0'] * n
        self.ecdh_keys = ['0'] * n
        self.incoming_verification_vector = ['0'] * n
        self.incoming_secret_key_contribution = ['0'] * n
        self.dkg_instance = dkg(t, n)

    def GeneratePolynomial(self):
        return self.dkg_instance.GeneratePolynomial()

    def VerificationVector(self, polynom):
        verification_vector = self.dkg_instance.VerificationVector(polynom)
        self.incoming_verification_vector[self.node_id] = verification_vector
        verification_vector_hexed = "0x"
        for coord in verification_vector:
            for elem in coord:
                temp = hex(int(elem[0]))[2:]
                while (len(temp) < 64):
                    temp = '0' + temp
                verification_vector_hexed += temp
                temp = hex(int(elem[1]))[2:]
                while len(temp) < 64 :
                    temp = '0' + temp
                verification_vector_hexed += temp
        return verification_vector_hexed

    def SecretKeyContribution(self, polynom):
        secret_key_contribution = self.dkg_instance.SecretKeyContribution(polynom)
        self.incoming_secret_key_contribution[self.node_id] = secret_key_contribution[self.node_id]
        to_broadcast = bytes('', 'utf-8')
        for i in range(self.n):
            # secret_key_contribution[i] = encrypt(self.public_keys[i], bytes(secret_key_contribution[i], 'utf-8'))
            # self.disposable_keys[i] = ecies.utils.generate_key() # is used for further verification in case any complaints will be sent
            # reciever_public_key = ecies.utils.hex2pub(self.public_keys[i])
            # aes_key = ecies.utils.derive(self.disposable_keys[i], reciever_public_key)
            # cipher_text = ecies.utils.aes_encrypt(aes_key, bytes(secret_key_contribution[i], 'utf-8'))
            # secret_key_contribution[i] = self.disposable_key[i].public_key.format(False) + cipher_text

            self.disposable_keys[i] = coincurve.keys.PrivateKey(coincurve.utils.get_valid_secret())
            self.ecdh_keys[i] = self.disposable_keys[i].ecdh(self.public_keys[i].format(compressed=False))
            #print(self.ecdh_keys[i])
            secret_key_contribution[i] = encrypt(secret_key_contribution[i], self.ecdh_keys[i])
            #print("LENGTH : ", secret_key_contribution[i], len(secret_key_contribution[i]), len(bytes(self.disposable_keys[i].public_key.format(compressed=False).hex()[2:], 'utf-8')))
            while len(secret_key_contribution[i]) < 32:
                secret_key_contribution[i] = bytes('0', 'utf-8') + secret_key_contribution[i]
            to_broadcast = to_broadcast + secret_key_contribution[i] + bytes(self.disposable_keys[i].public_key.format(compressed=False).hex()[2:], 'utf-8')
            #print(len(to_broadcast))
        return to_broadcast

    def Broadcast(self, dkg_contract):
        polynom = self.GeneratePolynomial()
        verification_vector = self.VerificationVector(polynom)
        secret_key_contribution = self.SecretKeyContribution(polynom)
        to_broadcst = dkg_contract.functions.broadcast(self.group_index, self.node_id, verification_vector, secret_key_contribution)
        res = sign_and_send(self.node_web3, to_broadcst, 1000000, self.wallet)
        x = await_receipt(self.node_web3, res)
        print(x)
        print("Everything is sent from", self.node_id, "node")

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
            smth.append((incoming_verification_vector[4], incoming_verification_vector[5]))
            to_verify.append(smth)
            incoming_verification_vector = incoming_verification_vector[6:]
        self.incoming_verification_vector[fromNode] = to_verify

    def RecieveSecretKeyContribution(self, fromNode, event):
        input = event['args']['secretKeyContribution']
        incoming_secret_key_contribution = []
        sent_public_keys = []
        while len(input) > 0:
            cur = input[:464]
            input = input[464:]
            sent_public_keys.append(cur[:64].hex())
            cur = cur[64:]
            while (cur[0] == 48):
                cur = cur[1:]
            incoming_secret_key_contribution.append(cur)
        ecdh_key = coincurve.keys.PrivateKey(self.wallet["private_key"]).ecdh(sent_public_keys[fromNode])
        incoming_secret_key_contribution[self.node_id] = encrypt(incoming_secret_key_contribution[self.node_id], ecdh_key)
        self.incoming_secret_key_contribution[fromNode] = incoming_secret_key_contribution[self.node_id].decode()

    def Verification(self, fromNode):
        return self.dkg_instance.Verification(self.node_id, self.incoming_secret_key_contribution[fromNode], self.incoming_verification_vector[fromNode])

    def SecretKeyShareCreate(self):
        self.secret_key_share = self.dkg_instance.SecretKeyShareCreate(self.incoming_secret_key_contribution)
        self.public_key = self.dkg_instance.GetPublicKeyFromSecretKey(self.secret_key_share)

    def SendComplaint(self, dkg_contract, toNode):
        to_complaint = dkg_contract.functions.complaint(self.group_index, self.node_id, toNode)
        res = sign_and_send(self.node_web3, to_complaint, 1000000, self.wallet)
        print(self.node_id, "-th sent a complaint on ", toNode, "-th node")

	# HERE SHOULD BE A RESPONSE FUNCTION
    def Response(self, dkg_contract, fromNodeIndex):
        to_response = dkg_contract.functions.response(self.group_index, fromNodeIndex, self.disposable_keys[fromNodeIndex].secret)
        res = sign_and_send(self.node_web3, to_response, 1000000, self.wallet)
        print(fromNodeIndex, "-th sent a response to ", self.node_id, "-th node")
        return

    def RecieveAll(self, fromNode, event):
        print("HERE\n")
        self.RecieveVerificationVector(fromNode, event)
        self.RecieveSecretKeyContribution(fromNode, event)
        if not self.Verification(fromNode):
            # schain cannot be created if at least one node is corrupted
            raise DkgVerificationError("Fatal error : user " + str(fromNode + 1) + " hasn't passed verification by user " + str(self.node_id + 1))
        self.SecretKeyShareCreate()
        print("All data was recieved and verified, secret key share was generated")

    def Allright(self, dkg_contract):
        allright = dkg_contract.functions.allright(self.group_index, self.node_id)
        res = sign_and_send(self.node_web3, allright, 1000000, self.wallet)
        print(self.node_id, "-th sent an allright note ")
