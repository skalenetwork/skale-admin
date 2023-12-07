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


def get_static_schain_info(env_type: str = ENV_TYPE) -> dict:
    static_params = get_static_params(env_type)
    return static_params['schain']


def get_static_node_info(schain_type: SchainType, env_type: str = ENV_TYPE) -> dict:
    static_params = get_static_params(env_type)
    return {**static_params['node']['common'], **static_params['node'][schain_type.name]}


def get_automatic_repair_option(env_type: str = ENV_TYPE) -> bool:
    static_params = get_static_params(env_type)
    return static_params['node']['common'].get('automatic-repair', True)
