""" SKALE test utilities """

import random
import string
import json


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


def get_bp_data(bp, request, params=None):
    data = bp.get(request, query_string=params).data
    return json.loads(data.decode('utf-8'))['data']


def post_bp_data(bp, request, params=None):
    data = bp.post(request, json=params).data
    return json.loads(data.decode('utf-8'))['data']
