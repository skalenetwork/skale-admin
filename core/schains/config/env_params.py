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
from core.schains.config.helper import get_environment_params
from tools.configs import ENV_TYPE


def get_static_schain_cmd(env_type: str = ENV_TYPE) -> list:
    environment_params = get_environment_params(env_type)
    return environment_params['schain_cmd']


def get_static_schain_info(env_type: str = ENV_TYPE) -> dict:
    environment_params = get_environment_params(env_type)
    return environment_params['schain']


def get_static_node_info(schain_type: SchainType, env_type: str = ENV_TYPE) -> dict:
    environment_params = get_environment_params(env_type)
    return {**environment_params['node']['common'], **environment_params['node'][schain_type.name]}
