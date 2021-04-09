""" SKALE test utilities """

import json
import os
import random
import string
import time

import mock
from mock import Mock, MagicMock

from skale import Skale
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet

from core.schains.runner import run_schain_container, run_ima_container
from tools.configs.web3 import ABI_FILEPATH
from tools.docker_utils import DockerUtils


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')


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


def get_schain_contracts_data(schain_name):
    """ Schain data mock in case if schain on contracts is not required """
    return {
        'name': schain_name,
        'owner': '0x1213123091a230923123213123',
        'indexInOwnerList': 0,
        'partOfNode': 0,
        'lifetime': 3600,
        'startDate': 1575448438,
        'deposit': 1000000000000000000,
        'index': 0,
        'active': True
    }


def run_simple_schain_container(schain_data: dict, dutils: DockerUtils):
    run_schain_container(schain_data, dutils=dutils)


def run_simple_schain_container_in_sync_mode(schain_data: dict,
                                             dutils: DockerUtils):
    public_key = "1:1:1:1"
    timestamp = time.time()

    class SnapshotAddressMock:
        def __init__(self):
            self.ip = '0.0.0.0'
            self.port = '8080'

    # Run schain container
    with mock.patch('core.schains.config.helper.get_skaled_http_snapshot_address',
                    return_value=SnapshotAddressMock()):
        run_schain_container(schain_data, public_key, timestamp, dutils=dutils)


def run_simple_ima_container(schain: dict, dutils: DockerUtils):
    run_ima_container(schain, mainnet_chain_id=1, dutils=dutils)


def init_web3_skale() -> Skale:
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return Skale(ENDPOINT, ABI_FILEPATH, wallet)


def init_web3_wallet() -> Web3Wallet:
    web3 = init_web3(ENDPOINT)
    return Web3Wallet(ETH_PRIVATE_KEY, web3)


def response_mock(status_code=0, json_data=None, cookies=None,
                  headers=None, raw=None):
    result = MagicMock()
    result.status_code = status_code
    result.json = MagicMock(return_value=json_data)
    result.cookies = cookies
    result.headers = headers
    result.raw = raw
    return result


def request_mock(response_mock):
    return Mock(return_value=response_mock)
