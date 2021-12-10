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

import os
import json
import time

import yaml
import errno
import logging
import itertools
import subprocess
from subprocess import PIPE

import requests

from filelock import FileLock
from jinja2 import Environment
from skale import Skale
from skale.wallets import BaseWallet

from tools.configs import INIT_LOCK_PATH
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, STATE_FILEPATH, ZERO_ADDRESS

logger = logging.getLogger(__name__)

POST_REQUEST_TIMEOUT = 30


def post_request(url, json, cookies=None):
    try:
        return requests.post(url, json=json, cookies=cookies,
                             timeout=POST_REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as err:
        logger.error(f'Post request failed with: {err}')
        return None


def read_json(path, mode='r'):
    with open(path, mode=mode, encoding='utf-8') as data_file:
        return json.load(data_file)


def write_json(path, content):
    with open(path, 'w') as outfile:
        json.dump(content, outfile, indent=4)


def init_file(path, content=None):
    if not os.path.exists(path):
        write_json(path, content)


def files(path):
    for file in os.listdir(path):
        if os.path.isfile(os.path.join(path, file)):
            yield file


def sanitize_filename(filename):
    return "".join(x for x in filename if x.isalnum() or x == '_')


def namedtuple_to_dict(tuple):
    return tuple._asdict()


def run_cmd(cmd, env={}, shell=False):
    logger.info(f'Running: {cmd}')
    res = subprocess.run(cmd, shell=shell, stdout=PIPE,
                         stderr=PIPE, env={**env, **os.environ})
    if res.returncode:
        logger.error('Error during shell execution:')
        logger.error(res.stderr.decode('UTF-8').rstrip())
        raise subprocess.CalledProcessError(res.returncode, cmd)
    return res


def format_output(res):
    return res.stdout.decode('UTF-8').rstrip(), \
            res.stderr.decode('UTF-8').rstrip()


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
    with open(destination, "w") as f:
        f.write(processed_template)


def wait_until_admin_inited():
    logger.info('Checking if skale-admin inited ...')
    lock = FileLock(INIT_LOCK_PATH)
    with lock:
        logger.info('Skale admin inited')


def init_skale(wallet: BaseWallet) -> Skale:
    return Skale(ENDPOINT, ABI_FILEPATH, wallet, state_path=STATE_FILEPATH)


def safe_load_yml(filepath):
    with open(filepath, 'r') as stream:
        return yaml.safe_load(stream)


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            return False
        else:
            raise err
    else:
        return True


def get_endpoint_call_speed(skale):
    scores = []
    for _ in range(10):
        start = time.time()
        result = skale.web3.eth.gasPrice
        if result:
            scores.append(time.time() - start)
    if len(scores) == 0:
        return None
    call_avg_speed = round(sum(scores) / len(scores), 2)
    logger.info(f'Endpoint call speed scores: {scores}, avg: {call_avg_speed}')
    return call_avg_speed


def is_zero_address(address: str) -> bool:
    """
    Returns true if provided string is equal to Ethereum zero address
    """
    return address == ZERO_ADDRESS
