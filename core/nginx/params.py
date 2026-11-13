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

import logging
import time

from skale_core.settings import get_settings

from core.config.schain.helper import get_static_params, get_static_params_fair
from tools.constants import NGINX_CHAINS_PATH
from tools.helper import is_fair

logger = logging.getLogger(__name__)


def get_nginx_params() -> dict:
    """The nginx section of the static params, empty when the stream has none"""
    env_type = get_settings().env_type
    static_params = get_static_params_fair(env_type) if is_fair() else get_static_params(env_type)
    return static_params.get('nginx') or {}


def is_rpc_proxy_due() -> bool:
    """The activation time in the static params has passed; 0 or absent means never"""
    timestamp = get_nginx_params().get('rpc_proxy_timestamp', 0)
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        logger.error(
            'nginx.rpc_proxy_timestamp %r is not an integer, the proxy stays off', timestamp
        )
        return False
    return 0 < timestamp <= time.time()


def is_rpc_proxy_enabled() -> bool:
    """Whether skaled should run on the internal ports with nginx serving the public ones"""
    return is_rpc_proxy_due() and NGINX_CHAINS_PATH.is_dir()
