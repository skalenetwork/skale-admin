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
import logging
import subprocess
import time
import requests
from subprocess import PIPE

from jinja2 import Environment


logger = logging.getLogger(__name__)


def post_request(url, json, cookies=None):
    try:
        return requests.post(url, json=json, cookies=cookies, timeout=10)
    except requests.exceptions.ConnectionError:
        print(f'Could not connect to {url}')
        return None


def read_json(path, mode='r'):
    with open(path, mode=mode, encoding='utf-8') as data_file:
        return json.load(data_file)


def write_json(path, content):
    with open(path, 'w') as outfile:
        json.dump(content, outfile, indent=4)
        outfile.close()


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
    res = subprocess.run(cmd, shell=shell, stdout=PIPE, stderr=PIPE, env={**env, **os.environ})
    if res.returncode:
        logger.error('Error during shell execution:')
        logger.error(res.stderr.decode('UTF-8').rstrip())
        raise subprocess.CalledProcessError(res.returncode, cmd)
    return res


def format_output(res):
    return res.stdout.decode('UTF-8').rstrip(), res.stderr.decode('UTF-8').rstrip()


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


class SkaleFilterError(Exception):
    pass


class SkaleFilter:
    def __init__(self, event_class, from_block, argument_filters,
                 to_block='latest',
                 timeout=4, retries=35):
        self.event_class = event_class
        self.from_block = from_block
        self.argument_filters = argument_filters
        self.to_block = to_block
        self.timeout = timeout
        self.retries = retries
        self.web3_filter = self.create_filter()

    def create_filter(self):
        return self.event_class.createFilter(
            fromBlock=self.from_block,
            toBlock=self.to_block,
            argument_filters=self.argument_filters
        )

    def get_events(self):
        events = None
        for _ in range(self.retries):
            try:
                events = self.web3_filter.get_all_entries()
            except Exception as err:
                self.web3_filter = self.create_filter()
                time.sleep(self.timeout)
                logger.error(
                    f'Retreiving events from filter failed with {err}'
                )
            else:
                break

        if events is None:
            raise SkaleFilterError('Filter get_events timed out')
        return events
