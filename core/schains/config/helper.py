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

from web3 import Web3
from Crypto.Hash import keccak


def fix_address(address):
    return Web3.toChecksumAddress(address)


def get_chain_id(schain_name):
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(schain_name.encode("utf-8"))
    hash_ = keccak_hash.hexdigest()
    hash_ = hash_[:13]			# use 52 bits
    return "0x" + hash_


def _string_to_storage(slot: int, string: str) -> dict:
    # https://solidity.readthedocs.io/en/develop/miscellaneous.html#bytes-and-string
    storage = dict()
    binary = string.encode()
    length = len(binary)
    if length < 32:
        binary += (2 * length).to_bytes(32 - length, 'big')
        storage[hex(slot)] = '0x' + binary.hex()
    else:
        storage[hex(slot)] = hex(2 * length + 1)

        keccak_hash = keccak.new(digest_bits=256)
        keccak_hash.update(slot.to_bytes(32, 'big'))
        offset = int.from_bytes(keccak_hash.digest(), 'big')

        def chunks(size, source):
            for i in range(0, len(source), size):
                yield source[i:i + size]

        for index, data in enumerate(chunks(32, binary)):
            if len(data) < 32:
                data += int(0).to_bytes(32 - len(data), 'big')
            storage[hex(offset + index)] = '0x' + data.hex()
    return storage
