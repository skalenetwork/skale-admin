#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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

from filestorage_predeployed import FILESTORAGE_ADDRESS

from core.schains.config.accounts import add_to_accounts
from tools.configs.schains import PRECOMPILED_CONTRACTS_FILEPATH
from tools.helper import read_json


def generate_precompiled_accounts(on_chain_owner: str) -> dict:
    """
    Generates accounts for SKALE precompiled contracts

    :param on_chain_owner: Address of the sChain owner on the chain
    :type on_chain_owner: str
    :returns: Dictionary with accounts
    :rtype: dict
    """
    accounts = {}
    precompileds = _get_precompiled_contracts()
    for address, precompiled in precompileds.items():
        if precompiled['precompiled'].get('restrictAccess'):
            handle_precompiled_permissions(precompiled, on_chain_owner)
        add_to_accounts(accounts, address, precompiled)
    return accounts


def handle_precompiled_permissions(precompiled: dict, on_chain_owner: str) -> None:
    for i, permission in enumerate(precompiled['precompiled']['restrictAccess']):
        if permission == 'fs':
            precompiled['precompiled']['restrictAccess'][i] = FILESTORAGE_ADDRESS
        if permission == 'schainOwner':
            precompiled['precompiled']['restrictAccess'][i] = on_chain_owner


def _get_precompiled_contracts():
    return read_json(PRECOMPILED_CONTRACTS_FILEPATH)
