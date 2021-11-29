#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019-Present SKALE Labs
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

from web3 import Web3
from skale.wallets.web3_wallet import public_key_to_address

from etherbase_predeployed import (
    UpgradeableEtherbaseUpgradeableGenerator, ETHERBASE_ADDRESS, ETHERBASE_IMPLEMENTATION_ADDRESS
)
from marionette_predeployed import (
    UpgradeableMarionetteGenerator, MARIONETTE_ADDRESS, MARIONETTE_IMPLEMENTATION_ADDRESS
)
from filestorage_predeployed import (
    UpgradeableFileStorageGenerator, FILESTORAGE_ADDRESS, FILESTORAGE_IMPLEMENTATION_ADDRESS
)
from deployment_controller_predeployed import (
    UpgradeableDeploymentControllerGenerator,
    DEPLOYMENT_CONTROLLER_ADDRESS,
    DEPLOYMENT_CONTROLLER_IMPLEMENTATION_ADDRESS
)
from multisigwallet_predeployed import MultiSigWalletGenerator, MULTISIGWALLET_ADDRESS
from predeployed_generator.openzeppelin.proxy_admin_generator import ProxyAdminGenerator
from ima_predeployed.generator import MESSAGE_PROXY_FOR_SCHAIN_ADDRESS, generate_contracts

from core.schains.config.generation import gen0, gen1
from core.schains.config.helper import (
    fix_address, _string_to_storage, get_context_contract
)

from core.schains.types import SchainType
from core.schains.limits import get_fs_allocated_storage

from tools.configs.schains import (SCHAIN_OWNER_ALLOC, NODE_OWNER_ALLOC,
                                   PRECOMPILED_CONTRACTS_FILEPATH)
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH
from tools.helper import read_json

logger = logging.getLogger(__name__)


PROXY_ADMIN_PREDEPLOYED_ADDRESS = '0xD1000000000000000000000000000000000000D1'


def generate_predeployed_section(
    schain_name: str,
    schain_type: SchainType,
    schain_nodes: list,
    on_chain_owner: str,
    mainnet_owner: str,
    erector_address: str,
    generation: int
) -> dict:
    """Main function used to generate dynamic accounts for the sChain config.
    For the params explanation please refer to the nested functions.

    :returns: Dictionary with accounts
    :rtype: dict
    """
    precompiled_section = {
        **generate_precompiled_accounts(),
        **generate_owner_accounts(on_chain_owner, erector_address, schain_nodes, generation),
        **generate_context_accounts(schain_name, on_chain_owner),
        **generate_ima_accounts(on_chain_owner, schain_name)
    }

    if gen0(generation):
        pass
    if gen1(generation):
        v1_precompiled_contracts = generate_v1_precompiled_contracts(
            schain_type=schain_type,
            on_chain_owner=on_chain_owner,
            mainnet_owner=mainnet_owner,
            erector_address=erector_address,
            message_proxy_for_schain_address=MESSAGE_PROXY_FOR_SCHAIN_ADDRESS
        )
        precompiled_section.update(v1_precompiled_contracts)

    return precompiled_section


def generate_v1_precompiled_contracts(
    schain_type: SchainType,
    on_chain_owner: str,
    mainnet_owner: str,
    erector_address: str,
    message_proxy_for_schain_address: str
) -> dict:
    proxy_admin_generator = ProxyAdminGenerator()
    proxy_admin_predeployed = proxy_admin_generator.generate_allocation(
        contract_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        owner_address=on_chain_owner
    )

    etherbase_generator = UpgradeableEtherbaseUpgradeableGenerator()
    etherbase_predeployed = etherbase_generator.generate_allocation(
        contract_address=ETHERBASE_ADDRESS,
        implementation_address=ETHERBASE_IMPLEMENTATION_ADDRESS,
        schain_owner=on_chain_owner,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        balance=SCHAIN_OWNER_ALLOC
    )

    marionette_generator = UpgradeableMarionetteGenerator()
    marionette_predeployed = marionette_generator.generate_allocation(
        contract_address=MARIONETTE_ADDRESS,
        implementation_address=MARIONETTE_IMPLEMENTATION_ADDRESS,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        schain_owner=mainnet_owner,
        marionette=on_chain_owner,
        owner=MULTISIGWALLET_ADDRESS,
        ima=message_proxy_for_schain_address,
    )

    allocated_storage = get_fs_allocated_storage(schain_type)
    filestorage_generator = UpgradeableFileStorageGenerator()
    filestorage_predeployed = filestorage_generator.generate_allocation(
        contract_address=FILESTORAGE_ADDRESS,
        implementation_address=FILESTORAGE_IMPLEMENTATION_ADDRESS,
        schain_owner=on_chain_owner,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        allocated_storage=allocated_storage
    )

    deployment_controller_generator = UpgradeableDeploymentControllerGenerator()
    deployment_controller_predeployed = deployment_controller_generator.generate_allocation(
        contract_address=DEPLOYMENT_CONTROLLER_ADDRESS,
        implementation_address=DEPLOYMENT_CONTROLLER_IMPLEMENTATION_ADDRESS,
        schain_owner=on_chain_owner,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS
    )

    multisigwallet_generator = MultiSigWalletGenerator()
    multisigwallet_predeployed = multisigwallet_generator.generate_allocation(
        contract_address=MULTISIGWALLET_ADDRESS,
        erector_addresses=[erector_address]
    )

    # TODO: add context manager SC (later)

    return {
        **proxy_admin_predeployed,
        **etherbase_predeployed,
        **marionette_predeployed,
        **filestorage_predeployed,
        **deployment_controller_predeployed,
        **multisigwallet_predeployed
    }


def generate_account(balance, code=None, storage={}, nonce=0):
    assert isinstance(code, str) or code is None
    assert isinstance(storage, dict) or storage is None
    account = {
        'balance': str(balance)
    }
    if code:
        account['code'] = code
        account['storage'] = storage
        account['nonce'] = str(nonce)
    return account


def get_precompiled_contracts():
    return read_json(PRECOMPILED_CONTRACTS_FILEPATH)


def add_to_accounts(accounts: dict, address: str, account: dict) -> None:
    accounts[fix_address(address)] = account


def generate_precompiled_accounts() -> dict:
    """Generates accounts for SKALE precompiled contracts

    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    precompileds = get_precompiled_contracts()
    for address, precompiled in precompileds.items():
        if precompiled['precompiled'].get('restrictAccess'):
            precompiled['precompiled']['restrictAccess'] = [FILESTORAGE_ADDRESS]
        add_to_accounts(accounts, address, precompiled)
    return accounts


def generate_owner_accounts(
    on_chain_owner: str,
    erector_address: str,
    schain_nodes: list,
    generation: int
) -> dict:
    """Generates accounts with allocation for sChain owner and sChain nodes owners

    :param on_chain_owner: Address of the sChain owner on the chain (only for gen 0)
    :type on_chain_owner: str
    :param erector_address: Erector address (only for gen 1)
    :type erector_address: str
    :param schain_nodes: List with nodes for the sChain
    :type schain_nodes_owners: list
    :param generation: Generation of the sChain
    :type generation: int
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    if gen0(generation):
        add_to_accounts(accounts, on_chain_owner, generate_account(SCHAIN_OWNER_ALLOC))
    if gen1(generation):
        add_to_accounts(accounts, erector_address, generate_account(SCHAIN_OWNER_ALLOC))
    for node in schain_nodes:
        node_owner = public_key_to_address(node['publicKey'])
        add_to_accounts(accounts, node_owner, generate_account(NODE_OWNER_ALLOC))
    return accounts


def generate_context_accounts(schain_name: dict, on_chain_owner: str) -> dict:
    """Generates accounts for the context predeployed SC

    :param schain_owner: Address of the sChain owner
    :type schain_owner: str
    :param schain_name: Name of the sChain
    :type schain_name: str
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    context_contract = get_context_contract()

    storage = {hex(0): str(Web3.toChecksumAddress(on_chain_owner))}
    storage = {**storage, **_string_to_storage(1, schain_name)}

    account = generate_account(
        balance=0,
        code=context_contract['bytecode'],
        storage=storage
    )
    add_to_accounts(accounts, context_contract['address'], account)
    return accounts


def generate_ima_accounts(on_chain_owner: str, schain_name: str) -> dict:
    """Generates accounts for the IMA contracts

    :param on_chain_owner: On-chain sChain owner
    :type on_chain_owner: str
    :param schain_name: sChain name
    :type schain_name: str
    :returns: Dictionary with accounts
    :rtype: dict
    """
    mainnet_ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)
    return generate_contracts(
        owner_address=on_chain_owner,
        schain_name=schain_name,
        contracts_on_mainnet=mainnet_ima_abi
    )
