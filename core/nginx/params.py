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
import socket
import time

from skale_core.settings import get_settings

from core.config.schain.helper import get_static_params, get_static_params_fair
from tools.constants import NGINX_CHAINS_PATH
from tools.helper import is_fair
from tools.node_options import NodeOptions

logger = logging.getLogger(__name__)

EXEMPT_HOSTS_TTL_SECONDS = 24 * 60 * 60

_resolved_hosts: dict[str, tuple[list[str], float]] = {}


def get_nginx_params() -> dict:
    """The nginx section of the static params, empty for streams released before the proxy"""
    env_type = get_settings().env_type
    static_params = get_static_params_fair(env_type) if is_fair() else get_static_params(env_type)
    return static_params.get('nginx') or {}


def is_rpc_proxy_enabled() -> bool:
    """Whether skaled should run on the internal ports with nginx serving the public ones"""
    params = get_nginx_params()
    if not params or not NGINX_CHAINS_PATH.is_dir():
        return False
    override = NodeOptions().rpc_proxy
    if override is not None:
        return override
    return bool(params.get('rpc_proxy', False))


def _resolve(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _resolve_cached(host: str) -> list[str]:
    """Re-resolved daily, the last answer is kept while DNS fails"""
    now = time.monotonic()
    cached = _resolved_hosts.get(host)
    if cached is None or now - cached[1] > EXEMPT_HOSTS_TTL_SECONDS:
        try:
            cached = _resolved_hosts[host] = (_resolve(host), now)
        except OSError:
            logger.warning('Could not resolve exempt host %s', host)
    return cached[0] if cached else []


def resolve_exempt_hosts(hosts: list[str]) -> list[str]:
    """IPv4 addresses of the SKALE RPC proxies, which skaled exempts from its limits"""
    return sorted({ip for host in hosts for ip in _resolve_cached(host)})
