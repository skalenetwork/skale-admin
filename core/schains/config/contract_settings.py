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
from dataclasses import dataclass

from skale.wallets.web3_wallet import public_key_to_address

from core.schains.config.helper import fix_address
from tools.helper import read_json

from tools.configs.ima import (
    MAINNET_IMA_ABI_FILEPATH, SCHAIN_IMA_ABI_FILEPATH, MAINNET_IMA_CONTRACTS, SCHAIN_IMA_CONTRACTS
)


logger = logging.getLogger(__name__)


@dataclass
class ContractSettings:
    """Dataclass that represents contractSettings key of the skaleConfig section"""
    common: dict
    ima: dict

    def to_dict(self):
        """Returns camel-case representation of the ContractSettings object"""
        return {
            'common': self.common,
            'IMA': self.ima,
        }


def generate_contract_settings(on_chain_owner: str, schain_nodes: list) -> ContractSettings:
    schain_ima_abi = read_json(SCHAIN_IMA_ABI_FILEPATH)
    mainnet_ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)

    ima_contracts_addresses = generate_ima_contracts_addresses(schain_ima_abi, mainnet_ima_abi)

    return ContractSettings(
        common={'enableContractLogMessages': True},
        ima={
            'ownerAddress': on_chain_owner,
            **ima_contracts_addresses
        }
    )


def get_address_from_abi_data(abi_data, name):
    return abi_data[f'{name}_address']


def generate_permitted_ima_contracts_info(schain_ima_abi):
    permitted_contracts = {}
    for name in SCHAIN_IMA_CONTRACTS:
        contract_filename = SCHAIN_IMA_CONTRACTS[name]['filename']
        permitted_contracts[contract_filename] = get_address_from_abi_data(schain_ima_abi, name)
    return permitted_contracts


def generate_mp_authorized_callers(schain_ima_abi, schain_owner, schain_nodes):
    mp_authorized_callers = {}
    for name in SCHAIN_IMA_CONTRACTS:
        address = get_address_from_abi_data(schain_ima_abi, name)
        mp_authorized_callers[address] = 1
    for node in schain_nodes:
        node_owner = public_key_to_address(node['publicKey'])
        acc_fx = fix_address(node_owner)
        if not mp_authorized_callers.get(acc_fx, None):
            mp_authorized_callers[acc_fx] = 1
    schain_owner_fx = fix_address(schain_owner)
    if not mp_authorized_callers.get(schain_owner_fx, None):
        mp_authorized_callers[schain_owner_fx] = 1
    return mp_authorized_callers


def generate_ima_contracts_addresses(schain_ima_abi, mainnet_ima_abi):
    addresses = {}
    for contracts in [(SCHAIN_IMA_CONTRACTS, schain_ima_abi),
                      (MAINNET_IMA_CONTRACTS, mainnet_ima_abi)]:
        for name in contracts[0]:
            contract_filename = contracts[0][name]['filename']
            addresses[contract_filename] = get_address_from_abi_data(contracts[1], name)
    return addresses
