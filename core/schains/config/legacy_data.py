#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2023-Present SKALE Labs
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

from tools.helper import read_json
from tools.configs import STATIC_ACCOUNTS_FOLDER, STATIC_GROUPS_FOLDER, ENV_TYPE


def static_accounts(schain_name: str) -> dict:
    return read_json(static_accounts_filepath(schain_name))


def is_static_accounts(schain_name: str) -> bool:
    return os.path.isfile(static_accounts_filepath(schain_name))


def static_accounts_filepath(schain_name: str) -> str:
    static_accounts_env_path = os.path.join(STATIC_ACCOUNTS_FOLDER, ENV_TYPE)
    if not os.path.isdir(static_accounts_env_path):
        return ''
    return os.path.join(static_accounts_env_path, f'schain-{schain_name}.json')


def static_groups(schain_name: str) -> dict:
    static_groups_env_path = static_groups_filepath(schain_name)
    if not os.path.isfile(static_groups_env_path):
        return {}
    groups = read_json(static_groups_env_path)
    prepared_groups = {}
    for plain_rotation_id, data in groups.items():
        rotation_id = int(plain_rotation_id)
        prepared_groups[rotation_id] = data
    return prepared_groups


def static_groups_filepath(schain_name: str) -> str:
    static_groups_env_path = os.path.join(STATIC_GROUPS_FOLDER, ENV_TYPE)
    if not os.path.isdir(static_groups_env_path):
        return ''
    return os.path.join(static_groups_env_path, f'schain-{schain_name}.json')
