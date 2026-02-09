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

import json
import logging
import os
from functools import wraps
from http import HTTPStatus

from flask import Response, g
from skale import SkaleManager
from skale.core.settings import SkaleSettings, get_settings
from skale.utils.cache import RedisCacheConfig
from skale.utils.web3_utils import init_web3

from core.manager_cache import ManagerCache
from core.node_config import NodeConfig
from core.utils.fair import init_fair_manager
from tools.constants.db import REDIS_URI
from tools.constants.web3 import CACHE_TTL_POLICY
from tools.helper import init_skale, is_fair
from tools.resources import rs
from tools.wallet_utils import init_wallet
from web import API_VERSION_PREFIX

logger = logging.getLogger(__name__)


def construct_response(status, data) -> Response:
    return Response(response=json.dumps(data), status=status, mimetype='application/json')


def construct_ok_response(data=None) -> Response:
    if data is None:
        data = {}
    return construct_response(HTTPStatus.OK, {'status': 'ok', 'payload': data})


def construct_err_response(msg=None, status_code=HTTPStatus.BAD_REQUEST) -> Response:
    if msg is None:
        msg = {}
    return construct_response(status_code, {'status': 'error', 'payload': msg})


def construct_key_error_response(absent_keys):
    keys_str = ', '.join(absent_keys)
    msg = f'Required arguments: {keys_str}'
    return construct_err_response(msg=msg)


def get_api_url(blueprint_name, method_name):
    return os.path.join(API_VERSION_PREFIX, blueprint_name, method_name)


def init_skale_from_node_config(node_config: NodeConfig) -> SkaleManager:
    st = get_settings(SkaleSettings)
    wallet = init_wallet(node_config, endpoint=str(st.endpoint), sgx_server_url=str(st.sgx_url))
    return init_skale(wallet)


def g_web3(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        st = get_settings()
        if is_fair():
            g.web3 = init_web3(str(st.endpoint))
        else:
            g.web3 = init_web3(
                str(st.endpoint),
                cache_config=RedisCacheConfig(
                    REDIS_URI,
                    method_ttl_policy=CACHE_TTL_POLICY,
                ),
            )
        return func(*args, **kwargs)

    return wrapper


def g_skale(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if getattr(g, 'wallet', None) is None:
            g.skale = init_skale_from_node_config(g.config)
            g.wallet = g.skale.wallet
        else:
            g.skale = init_skale(g.wallet)
        return func(*args, **kwargs)

    return wrapper


def g_fair(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if getattr(g, 'wallet', None) is None:
            g.fair = init_fair_manager(node_config=g.config)
            g.wallet = g.fair.wallet
        else:
            g.fair = init_fair_manager(wallet=g.wallet)
        return func(*args, **kwargs)

    return wrapper


def g_fair_no_wallet(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        g.fair = init_fair_manager()
        return func(*args, **kwargs)

    return wrapper


def g_manager_cache(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        g.manager_cache = ManagerCache(rs, g.skale, g.config.id)
        return func(*args, **kwargs)

    return wrapper
