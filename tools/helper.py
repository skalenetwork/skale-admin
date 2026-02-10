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

import hashlib
import itertools
import json
import logging
import os
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from subprocess import PIPE
from typing import cast

import requests
import yaml
from filelock import FileLock
from jinja2 import Environment
from skale import SkaleManager
from skale.core.settings import BaseNodeSettings, SkaleSettings, get_node_settings, get_settings
from skale.types.node import NodeId
from skale.utils.cache import RedisCacheConfig
from skale.wallets import BaseWallet
from web3 import Web3

from tools.constants import CONTAINERS_FILEPATH, INIT_LOCK_PATH
from tools.constants.db import REDIS_URI
from tools.constants.web3 import CACHE_TTL_POLICY, ZERO_ADDRESS

logger = logging.getLogger(__name__)

POST_REQUEST_TIMEOUT = 30


def post_request(url, json, cookies=None, timeout=None):
    timeout = timeout or POST_REQUEST_TIMEOUT
    try:
        return requests.post(url, json=json, cookies=cookies, timeout=timeout)
    except requests.exceptions.RequestException as err:
        logger.error(f'Post request failed with: {err}')
        return None


def read_json(path: Path | str, mode='r'):
    with open(path, mode=mode, encoding='utf-8') as data_file:
        return json.load(data_file)


def write_json(path: Path | str, content):
    with open(path, 'w') as outfile:
        json.dump(content, outfile, indent=4)


def run_cmd(cmd, env={}, shell=False):
    logger.info(f'Running: {cmd}')
    res = subprocess.run(cmd, shell=shell, stdout=PIPE, stderr=PIPE, env={**os.environ, **env})
    if res.returncode:
        logger.error('Error during shell execution:')
        logger.error(res.stderr.decode('UTF-8').rstrip())
        raise subprocess.CalledProcessError(res.returncode, cmd)
    return res


def merged_unique(*args):
    seen = set()
    for item in itertools.chain(*args):
        if item not in seen:
            yield item
            seen.add(item)


def process_template(source, destination, data):
    """
    :param source: j2 template source path
    :param destination: out file path
    :param data: dictionary with fields for template
    :return: Nothing
    """
    template = None
    with open(source) as template_file:
        template = template_file.read()
    processed_template = Environment().from_string(template).render(data)
    with open(destination, 'w') as f:
        f.write(processed_template)


def wait_until_admin_inited():
    logger.info('Checking if skale-admin inited ...')
    lock = FileLock(INIT_LOCK_PATH)
    with lock:
        logger.info('Skale admin inited')


def init_skale(wallet: BaseWallet | None) -> SkaleManager:
    st = get_settings((SkaleSettings, BaseNodeSettings))
    return SkaleManager(
        str(st.endpoint),
        st.manager_contracts,
        wallet,
        enable_stats=True,
        redis_cache_config=RedisCacheConfig(
            REDIS_URI,
            method_ttl_policy=CACHE_TTL_POLICY,
        ),
    )


def safe_load_yml(filepath):
    with open(filepath, 'r') as stream:
        return yaml.safe_load(stream)


def check_pid(pid):
    """Check For the existence of a unix pid."""
    try:
        # os.kill() with signal 0 doesn't kill the process, just tests if it exists.
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_endpoint_call_speed(web3: Web3) -> float | None:
    duration: float | None = None
    start = time.time()
    result = web3.eth.gas_price
    if result:
        duration = time.time() - start
    logger.info(f'Endpoint call speed: {duration}')
    return duration


def is_node_part_of_chain(skale, schain_name, node_id) -> bool:
    if not skale.schains_internal.is_schain_exist(schain_name):
        return False
    node_ids = skale.schains_internal.node_ids_for_schain(schain_name)
    return node_id in node_ids


def is_zero_address(address: str) -> bool:
    return address == ZERO_ADDRESS


def is_address_contract(web3, address) -> bool:
    return web3.eth.get_code(address) != b''


def no_hyphens(name: str) -> str:
    return name.replace('-', '_')


def is_fair() -> bool:
    node_st = get_node_settings()
    return node_st.node_type == 'fair'


def is_passive() -> bool:
    node_st = get_node_settings()
    return node_st.node_mode == 'passive'


def cast_manager_to_fair_node_id(manager_node_id: int) -> NodeId:
    return cast(NodeId, manager_node_id)


def dict_to_hash(d: dict) -> str:
    return hashlib.md5(json.dumps(d).encode()).hexdigest()


@lru_cache
def containers_info() -> dict:
    return read_json(CONTAINERS_FILEPATH)
