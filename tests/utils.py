""" SKALE test utilities """

import os
import json
import random
import string
import time
from contextlib import contextmanager

from mock import Mock, MagicMock

from skale import Skale, SkaleIma
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet

from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.schains.config.main import save_schain_config
from core.schains.config.directory import get_schain_config
from core.schains.firewall.types import IHostFirewallController, IpRange
from core.schains.firewall import SChainFirewallManager, SChainRuleController
from core.schains.runner import (
    get_image_name,
    run_schain_container,
    run_ima_container,
    get_container_info
)

from tools.docker_utils import DockerUtils
from tools.helper import run_cmd
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.configs.web3 import ABI_FILEPATH

from web.models.schain import upsert_schain_record


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
IMA_ABI_FILEPATH = os.getenv('IMA_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'ima.json')


ETH_AMOUNT_PER_NODE = 1
CONFIG_STREAM = "1.0.0-testnet"


ALLOWED_RANGES = [
    IpRange('1.1.1.1', '2.2.2.2'),
    IpRange('3.3.3.3', '4.4.4.4')
]


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
        'mainnetOwner': '0x1213123091a230923123213123',
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
    run_schain_container(schain_data, public_key, timestamp, dutils=dutils)


def run_simple_ima_container(schain: dict, dutils: DockerUtils):
    image = get_image_name(type=IMA_CONTAINER)
    run_ima_container(schain, mainnet_chain_id=1, image=image, dutils=dutils)


def init_web3_skale() -> Skale:
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return init_skale_from_wallet(wallet)


def init_skale_from_wallet(wallet) -> Skale:
    return Skale(ENDPOINT, ABI_FILEPATH, wallet)


def init_skale_ima():
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return SkaleIma(ENDPOINT, IMA_ABI_FILEPATH, wallet)


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


class HostTestFirewallController(IHostFirewallController):
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


class SChainTestFirewallManager(SChainFirewallManager):
    def create_host_controller(self):
        return HostTestFirewallController()


class SChainTestRuleController(SChainRuleController):
    def create_firewall_manager(self):
        return SChainTestFirewallManager(
            self.name,
            self.base_port,
            self.base_port + self.ports_per_schain
        )


def get_test_rule_controller(
    name,
    base_port=None,
    own_ip=None,
    node_ips=[],
    sync_agent_ranges=[],
    synced=False
):
    rc = SChainTestRuleController(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )
    if synced:
        rc.sync()
    return rc


@contextmanager
def no_schain_artifacts(schain_name, dutils):
    try:
        yield
    finally:
        remove_schain_container(schain_name, dutils=dutils)
        time.sleep(10)
        remove_schain_volume(schain_name, dutils=dutils)
        remove_config_dir(schain_name)


def run_custom_schain_container(dutils, schain_name, entrypoint):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_name)
    return dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint=entrypoint
    )


def upsert_schain_record_with_config(name, version=None):
    version = version or CONFIG_STREAM
    r = upsert_schain_record(name)
    r.set_config_version(version)
    return r
