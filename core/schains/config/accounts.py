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


from core.schains.config.helper import fix_address


def generate_account(balance, code=None, storage={}, nonce=0):
    if code and not isinstance(code, str):
        raise ValueError('Code must be a str or None')
    if storage and not isinstance(storage, dict):
        raise ValueError('Code must be a dict or None')
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
