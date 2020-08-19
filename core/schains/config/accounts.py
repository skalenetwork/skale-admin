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

from web3 import Web3
from skale.wallets.web3_wallet import public_key_to_address

from core.schains.config.helper import fix_address, _string_to_storage, get_context_contract
from core.schains.filestorage import compose_filestorage_info
from core.schains.helper import read_ima_data
from core.schains.volume import get_resource_allocation_info, get_allocation_part_name

from tools.configs.schains import SCHAIN_OWNER_ALLOC, NODE_OWNER_ALLOC
from tools.configs.ima import PRECOMPILED_IMA_CONTRACTS

logger = logging.getLogger(__name__)


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


def add_to_accounts(accounts: dict, address: str, account: dict) -> None:
    accounts[fix_address(address)] = account


def generate_owner_accounts(schain_owner: str, schain_nodes: list) -> dict:
    """Generates accounts with allocation for sChain owner and sChain nodes owners

    :param schain_owner: Address of the sChain owner
    :type schain_owner: str
    :param schain_nodes: List with nodes for the sChain
    :type schain_nodes_owners: list
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    add_to_accounts(accounts, schain_owner, generate_account(SCHAIN_OWNER_ALLOC))
    for node in schain_nodes:
        node_owner = public_key_to_address(node['publicKey'])
        add_to_accounts(accounts, node_owner, generate_account(NODE_OWNER_ALLOC))
    return accounts


def generate_context_accounts(schain: dict) -> dict:
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

    storage = {hex(0): str(Web3.toChecksumAddress(schain['owner']))}
    storage = {**storage, **_string_to_storage(1, schain['name'])}

    account = generate_account(
        balance=0,
        code=context_contract['bytecode'],
        storage=storage
    )
    add_to_accounts(accounts, context_contract['address'], account)
    return accounts


def generate_fs_accounts(schain: dict) -> dict:
    """Generates accounts for the Filestorage

    :param schain: sChain structure
    :type schain: dict
    :returns: Dictionary with accounts
    :rtype: dict
    """
    resource_allocation = get_resource_allocation_info()
    allocation_part_name = get_allocation_part_name(schain)
    schin_internal_limits = resource_allocation['schain'][allocation_part_name]

    filestorage_info = compose_filestorage_info(schin_internal_limits)
    accounts = {}
    account = generate_account(
        balance=0,
        code=filestorage_info['bytecode'],
        storage=filestorage_info['storage']
    )
    add_to_accounts(
        accounts=accounts,
        address=filestorage_info['address'],
        account=account
    )
    return accounts


def generate_ima_accounts():
    """Generates accounts for the IMA

    :returns: Dictionary with accounts
    :rtype: dict
    """
    ima_data = read_ima_data()
    accounts = {}
    for contract_name in PRECOMPILED_IMA_CONTRACTS:
        add_to_accounts(
            accounts=accounts,
            address=ima_data[f'{contract_name}_address'],
            account=generate_account(
                balance=0,
                code=ima_data[f'{contract_name}_bytecode']
            )
        )
    return accounts


def generate_dynamic_accounts(schain: dict, schain_nodes: list) -> dict:
    """Main function used to generate dynamic accounts for the sChain config.
    For the params explanation please refer to the nested functions.

    :returns: Dictionary with accounts
    :rtype: dict
    """
    return {
        **generate_owner_accounts(schain['owner'], schain_nodes),
        **generate_context_accounts(schain),
        **generate_fs_accounts(schain),
        **generate_ima_accounts()
    }
