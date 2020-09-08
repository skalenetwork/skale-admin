""" SKALE test utilities """

import json
import os
import random
import string
from pathlib import Path

import pytest

from tools.configs.schains import SCHAINS_DIR_PATH


class FailedAPICall(Exception):
    pass


def generate_random_ip():
    return '.'.join('%s' % random.randint(0, 255) for i in range(4))


def generate_random_name(len=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=len))


def generate_random_port():
    return random.randint(0, 60000)


def generate_random_node_data():
    return generate_random_ip(), generate_random_ip(), generate_random_port(), \
        generate_random_name()


def generate_random_schain_data():
    lifetime_seconds = 3600  # 1 hour
    type_of_nodes = 1
    return type_of_nodes, lifetime_seconds, generate_random_name()


def get_bp_data(bp, request, params=None, full_data=False, **kwargs):
    data = bp.get(request, query_string=params, **kwargs).data
    if full_data:
        return data

    return json.loads(data.decode('utf-8'))


def post_bp_data(bp, request, params=None, full_response=False, **kwargs):
    data = bp.post(request, json=params).data
    if full_response:
        return json.loads(data.decode('utf-8'))

    return json.loads(data.decode('utf-8'))
