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
import yaml
import logging
import subprocess
import requests
from subprocess import PIPE

from filelock import FileLock
from jinja2 import Environment
from skale import Skale
from skale.wallets import BaseWallet, RPCWallet

from tools.configs import INIT_LOCK_PATH
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, STATE_FILEPATH, TM_URL

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


def read_file(path):
    file = open(path, 'r')
    text = file.read()
    file.close()
    return text


def process_template(source, destination, data):
    """
    :param source: j2 template source path
    :param destination: out file path
    :param data: dictionary with fields for template
    :return: Nothing
    """
    template = read_file(source)
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


def init_defualt_wallet() -> Skale:
    return RPCWallet(TM_URL)


def safe_load_yml(filepath):
    with open(filepath, 'r') as stream:
        return yaml.safe_load(stream)


def is_btrfs_loaded():
    from sh import lsmod
    modules = list(
        filter(lambda s: s.startswith('btrfs'), lsmod().split('\n'))
    )
    return modules != []
