#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026-Present SKALE Labs
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

from skale_core.settings import get_settings

from core.config.schain.helper import get_static_params, get_static_params_fair
from tools.constants import NGINX_CHAINS_PATH
from tools.helper import is_fair


def get_nginx_params() -> dict:
    """The nginx section of the static params, empty for streams released before the proxy"""
    env_type = get_settings().env_type
    static_params = get_static_params_fair(env_type) if is_fair() else get_static_params(env_type)
    return static_params.get('nginx') or {}


def is_rpc_proxy_enabled() -> bool:
    """Whether skaled should run on the internal ports with nginx serving the public ones"""
    return bool(get_nginx_params().get('rpc_proxy')) and NGINX_CHAINS_PATH.is_dir()
