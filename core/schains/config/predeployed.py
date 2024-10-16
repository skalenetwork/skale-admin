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

from skale.dataclasses.schain_options import AllocationType
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
from config_controller_predeployed import (
    UpgradeableConfigControllerGenerator,
    CONFIG_CONTROLLER_ADDRESS,
    CONFIG_CONTROLLER_IMPLEMENTATION_ADDRESS
)
from multisigwallet_predeployed import MultiSigWalletGenerator, MULTISIGWALLET_ADDRESS
from predeployed_generator.openzeppelin.proxy_admin_generator import ProxyAdminGenerator
from ima_predeployed.generator import MESSAGE_PROXY_FOR_SCHAIN_ADDRESS, generate_contracts
from context_predeployed import ContextGenerator, CONTEXT_ADDRESS

from core.schains.config.accounts import add_to_accounts, generate_account
from core.schains.config.generation import Gen

from core.schains.types import SchainType
from core.schains.limits import get_fs_allocated_storage

from tools.configs.schains import SCHAIN_OWNER_ALLOC, NODE_OWNER_ALLOC, ETHERBASE_ALLOC
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH
from tools.helper import read_json
from importlib.metadata import version

logger = logging.getLogger(__name__)


PROXY_ADMIN_PREDEPLOYED_ADDRESS = '0xD1000000000000000000000000000000000000D1'


def generate_predeployed_accounts(
    schain_name: str,
    schain_type: SchainType,
    allocation_type: AllocationType,
    schain_nodes: list,
    on_chain_owner: str,
    mainnet_owner: str,
    originator_address: str,
    generation: int
) -> dict:
    """Main function used to generate dynamic accounts for the sChain config.
    For the params explanation please refer to the nested functions.

    :returns: Dictionary with accounts
    :rtype: dict
    """
    predeployed_section = {
        **generate_owner_accounts(on_chain_owner, originator_address, schain_nodes, generation),
        **generate_ima_accounts(on_chain_owner, schain_name)
    }

    if generation >= Gen.ONE:
        v1_predeployed_contracts = generate_v1_predeployed_contracts(
            schain_type=schain_type,
            allocation_type=allocation_type,
            on_chain_owner=on_chain_owner,
            mainnet_owner=mainnet_owner,
            originator_address=originator_address,
            message_proxy_for_schain_address=MESSAGE_PROXY_FOR_SCHAIN_ADDRESS,
            schain_name=schain_name
        )
        predeployed_section.update(v1_predeployed_contracts)
    if generation == Gen.ZERO:
        pass  # no predeployeds for gen 0
    return predeployed_section


def generate_v1_predeployed_contracts(
    schain_type: SchainType,
    allocation_type: AllocationType,
    on_chain_owner: str,
    mainnet_owner: str,
    originator_address: str,
    message_proxy_for_schain_address: str,
    schain_name: str
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
        ether_managers=[message_proxy_for_schain_address],
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        balance=ETHERBASE_ALLOC
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

    allocated_storage = get_fs_allocated_storage(schain_type, allocation_type)
    filestorage_generator = UpgradeableFileStorageGenerator()
    filestorage_predeployed = filestorage_generator.generate_allocation(
        contract_address=FILESTORAGE_ADDRESS,
        implementation_address=FILESTORAGE_IMPLEMENTATION_ADDRESS,
        schain_owner=on_chain_owner,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS,
        allocated_storage=allocated_storage,
        version=version('filestorage_predeployed')
    )

    config_generator = UpgradeableConfigControllerGenerator()
    config_controller_predeployed = config_generator.generate_allocation(
        contract_address=CONFIG_CONTROLLER_ADDRESS,
        implementation_address=CONFIG_CONTROLLER_IMPLEMENTATION_ADDRESS,
        schain_owner=on_chain_owner,
        proxy_admin_address=PROXY_ADMIN_PREDEPLOYED_ADDRESS
    )

    multisigwallet_generator = MultiSigWalletGenerator()
    multisigwallet_predeployed = multisigwallet_generator.generate_allocation(
        contract_address=MULTISIGWALLET_ADDRESS,
        originator_addresses=[originator_address]
    )

    context_generator = ContextGenerator()
    context_predeployed = context_generator.generate_allocation(
        CONTEXT_ADDRESS,
        schain_owner=on_chain_owner,
        schain_name=schain_name
    )

    return {
        **proxy_admin_predeployed,
        **etherbase_predeployed,
        **marionette_predeployed,
        **filestorage_predeployed,
        **config_controller_predeployed,
        **multisigwallet_predeployed,
        **context_predeployed
    }


def generate_owner_accounts(
    on_chain_owner: str,
    originator_address: str,
    schain_nodes: list,
    generation: int
) -> dict:
    """
    Generates accounts with allocation for sChain owner and sChain nodes owners

    :param on_chain_owner: Address of the sChain owner on the chain (only for gen 0)
    :type on_chain_owner: str
    :param originator_address: Originator address (only for gen 1)
    :type originator_address: str
    :param schain_nodes: List with nodes for the sChain
    :type schain_nodes_owners: list
    :param generation: Generation of the sChain
    :type generation: int
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    if generation >= Gen.ONE:
        add_to_accounts(accounts, originator_address, generate_account(SCHAIN_OWNER_ALLOC))
    if generation == Gen.ZERO:
        add_to_accounts(accounts, on_chain_owner, generate_account(SCHAIN_OWNER_ALLOC))
    for node in schain_nodes:
        node_owner = public_key_to_address(node['publicKey'])
        add_to_accounts(accounts, node_owner, generate_account(NODE_OWNER_ALLOC))
    return accounts


def generate_ima_accounts(on_chain_owner: str, schain_name: str) -> dict:
    """
    Generates accounts for the IMA contracts

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
