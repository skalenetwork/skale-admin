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

from core.schains.config.helper import (fix_address, _string_to_storage,
                                        get_context_contract, get_deploy_controller_contract,
                                        calculate_deployment_owner_slot)
from core.schains.filestorage import compose_filestorage_info, get_filestorage_info

from core.schains.limits import get_schain_limit
from core.schains.types import MetricType
from core.ima.schain import generate_ima_accounts

from tools.configs.schains import (SCHAIN_OWNER_ALLOC, NODE_OWNER_ALLOC,
                                   PRECOMPILED_CONTRACTS_FILEPATH)
from tools.helper import read_json

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
    filestorage_address = get_filestorage_info()['address']
    for address, precompiled in precompileds.items():
        if precompiled['precompiled'].get('restrictAccess'):
            precompiled['precompiled']['restrictAccess'] = [filestorage_address]
        add_to_accounts(accounts, address, precompiled)
    return accounts


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


def generate_deploy_controller_accounts(schain_owner: str) -> dict:
    """Generates accounts for the deploy controller predeployed SC

    :param schain_owner: Address of the sChain owner
    :type schain_owner: str
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    deploy_controller_contract = get_deploy_controller_contract()
    owner_slot = calculate_deployment_owner_slot(schain_owner)
    bytes_true = '0x01'

    storage = {owner_slot: bytes_true}

    account = generate_account(
        balance=0,
        code=deploy_controller_contract['bytecode'],
        storage=storage
    )
    add_to_accounts(accounts, deploy_controller_contract['address'], account)
    return accounts


def generate_fs_accounts(schain: dict) -> dict:
    """Generates accounts for the Filestorage

    :param schain: sChain structure
    :type schain: dict
    :returns: Dictionary with accounts
    :rtype: dict
    """
    volume_limits = get_schain_limit(schain, MetricType.volume_limits)
    filestorage_info = compose_filestorage_info(volume_limits)
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


def generate_dynamic_accounts(schain: dict, schain_nodes: list) -> dict:
    """Main function used to generate dynamic accounts for the sChain config.
    For the params explanation please refer to the nested functions.

    :returns: Dictionary with accounts
    :rtype: dict
    """
    return {
        **generate_precompiled_accounts(),
        **generate_owner_accounts(schain['owner'], schain_nodes),
        **generate_context_accounts(schain),
        **generate_deploy_controller_accounts(schain['owner']),
        **generate_fs_accounts(schain),
        **generate_ima_accounts(schain['owner'], schain['name'])
    }
