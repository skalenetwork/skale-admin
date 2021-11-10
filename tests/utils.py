""" SKALE test utilities """

import json
import os
import random
import string
import time
from functools import partial

import mock
from mock import Mock, MagicMock

from skale import Skale, SkaleIma
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet

from core.schains.config.generator import save_schain_config
from core.schains.config.helper import get_schain_config
from core.schains.firewall.types import IHostFirewallManager, PORTS_PER_SCHAIN
from core.schains.firewall import SChainFirewallManager, SChainRuleController
from core.schains.runner import run_schain_container, run_ima_container

from tools.docker_utils import DockerUtils
from tools.helper import run_cmd


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'manager.json')
TEST_IMA_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'ima.json')


CONTAINERS_JSON = {
  "schain": {
    "name": "skalenetwork/schain",
    "version": "3.7.5-beta.0",
    "custom_args": {
      "ulimits_list": [
        {
          "name": "core",
          "soft": -1,
          "hard": -1
        }
      ],
      "logs": {
        "max-size": "250m",
        "max-file": "5"
      }
    },
    "args": {
      "security_opt": [
        "seccomp=unconfined"
      ],
      "restart_policy": {
        "MaximumRetryCount": 0,
        "Name": "on-failure"
      },
      "network": "host",
      "cap_add": [
        "SYS_PTRACE",
        "SYS_ADMIN"
      ]
    }
  },
  "ima": {
    "name": "skalenetwork/ima",
    "version": "1.0.0-develop.208",
    "custom_args": {},
    "args": {
      "restart_policy": {
        "MaximumRetryCount": 10,
        "Name": "on-failure"
      },
      "network": "host"
    }
  }
}


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


def generate_cert(cert_path, key_path):
    return run_cmd([
        'openssl', 'req',
        '-newkey', 'rsa:4096',
        '-x509',
        '-sha256',
        '-days', '365',
        '-nodes',
        '-subj', '/',
        '-out', cert_path,
        '-keyout', key_path
    ])


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
        return data
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
    timestamp = int(time.time())

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
    return init_skale_from_wallet(wallet)


def init_skale_from_wallet(wallet) -> Skale:
    return Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)


def init_skale_ima():
    print(ENDPOINT, TEST_IMA_ABI_FILEPATH)
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return SkaleIma(ENDPOINT, TEST_IMA_ABI_FILEPATH, wallet)


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


def alter_schain_config(schain_name: str, public_key: str) -> None:
    """
    Fix config to make skaled work with a single node (mine blocks, etc)
    """
    config = get_schain_config(schain_name)
    node = config['skaleConfig']['sChain']['nodes'][0]
    node['publicKey'] = public_key
    config['skaleConfig']['sChain']['nodes'] = [node]
    save_schain_config(config, schain_name)


class HostFirewallManagerMock(IHostFirewallManager):
    def __init__(self):
        self._rules = set()

    def add_rule(self, srule):
        self._rules.add(srule)

    def remove_rule(self, srule):
        if self.has_rule(srule):
            self._rules.remove(srule)

    @property
    def rules(self):
        return iter(self._rules)

    def has_rule(self, srule):
        return srule in self._rules


def get_test_rc(
    name,
    base_port,
    own_ip,
    node_ips,
    sync_agent_ranges=[],
    synced=False
):
    hm = HostFirewallManagerMock()
    fm = SChainFirewallManager(
        name,
        base_port,
        base_port + PORTS_PER_SCHAIN,
        hm
    )
    rc = SChainRuleController(
        fm,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )
    if synced:
        rc.sync()
    return rc


get_test_rc_synced = partial(get_test_rc, synced=True)
