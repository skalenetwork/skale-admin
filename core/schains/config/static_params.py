#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022-Present SKALE Labs
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

from core.schains.types import SchainType
from core.schains.config.helper import get_static_params
from tools.configs import ENV_TYPE


def get_static_schain_cmd(env_type: str = ENV_TYPE) -> list:
    static_params = get_static_params(env_type)
    return static_params['schain_cmd']


def get_static_schain_info(schain_name: str, env_type: str = ENV_TYPE) -> dict:
    static_params = get_static_params(env_type)
    static_params_schain = static_params['schain']
    processed_params = {}
    for param_name, param in static_params_schain.items():
        processed_params[param_name] = get_schain_static_param(param, schain_name)
    return processed_params


def get_schain_static_param(static_param_schain: dict | int, schain_name: str) -> int:
    if isinstance(static_param_schain, int):
        return static_param_schain
    elif isinstance(static_param_schain, dict) and schain_name in static_param_schain:
        return static_param_schain[schain_name]
    else:
        return static_param_schain.get('default', None)


def get_static_node_info(schain_type: SchainType, env_type: str = ENV_TYPE) -> dict:
    static_params = get_static_params(env_type)
    return {**static_params['node']['common'], **static_params['node'][schain_type.name]}


def get_automatic_repair_option(env_type: str = ENV_TYPE) -> bool:
    static_params = get_static_params(env_type)
    node_params = static_params['node']
    if 'admin' in node_params:
        return node_params['admin'].get('automatic_repair', True)
    return True
