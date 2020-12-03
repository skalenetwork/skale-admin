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
from core.schains.helper import read_ima_data
from tools.configs.ima import PRECOMPILED_IMA_CONTRACTS

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


def generate_contract_settings(schain_owner: str, schain_nodes: list) -> ContractSettings:
    ima_data = read_ima_data()
    permitted_contracts = generate_permitted_ima_contracts_info(ima_data)
    mp_authorized_callers = generate_mp_authorized_callers(ima_data, schain_owner,
                                                           schain_nodes)
    ima_contracts_addresses = generate_ima_contracts_addresses(ima_data)
    return ContractSettings(
        common={'enableContractLogMessages': False},
        ima={
            'ownerAddress': schain_owner,
            'variables': {
                'LockAndData': {
                    'permitted': permitted_contracts
                },
                'MessageProxy': {
                    'mapAuthorizedCallers': mp_authorized_callers
                }
            },
            **ima_contracts_addresses
        }
    )


def get_contract_address_from_ima_data(ima_data, name):
    return ima_data[f'{name}_address']


def generate_permitted_ima_contracts_info(ima_data):
    permitted_contracts = {}
    for name in PRECOMPILED_IMA_CONTRACTS:
        contract_filename = PRECOMPILED_IMA_CONTRACTS[name]['filename']
        permitted_contracts[contract_filename] = get_contract_address_from_ima_data(ima_data, name)
    return permitted_contracts


def generate_mp_authorized_callers(ima_data, schain_owner, schain_nodes):
    mp_authorized_callers = {}
    for name in PRECOMPILED_IMA_CONTRACTS:
        address = get_contract_address_from_ima_data(ima_data, name)
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


def generate_ima_contracts_addresses(ima_data):
    ima_contracts_addresses = {}
    for name in PRECOMPILED_IMA_CONTRACTS:
        contract_filename = PRECOMPILED_IMA_CONTRACTS[name]['filename']
        address = get_contract_address_from_ima_data(ima_data, name)
        ima_contracts_addresses[contract_filename] = address
    return ima_contracts_addresses
