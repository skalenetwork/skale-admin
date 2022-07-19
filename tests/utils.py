""" SKALE test utilities """

import json
import logging
import os
import random
import string
import time
from contextlib import contextmanager
from dataclasses import dataclass

from mock import Mock, MagicMock

from skale import Skale, SkaleIma
from skale.contracts.manager.nodes import NodeStatus
from skale.utils.account_tools import send_ether
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME
from skale.utils.web3_utils import init_web3
from skale.wallets import SgxWallet, Web3Wallet

from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.node import Node
from core.schains.config.main import save_schain_config
from core.schains.config.helper import get_schain_config
from core.schains.firewall.types import IHostFirewallController
from core.schains.firewall import SChainFirewallManager, SChainRuleController
from core.schains.runner import run_schain_container, run_ima_container, get_container_info

from tools.docker_utils import DockerUtils
from tools.helper import run_cmd
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.configs.containers import SCHAIN_CONTAINER


logger = logging.getLogger(__name__)

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'manager.json')
TEST_IMA_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'ima.json')
TEST_ETH_AMOUNT = 1
TEST2_TYPE = 1
TEST_SRW_FUND_VALUE = 3000000000000000000
DEFAULT_SCHAIN_LIFETIME = 3600  # 1 hour


CONTAINERS_JSON = {
  "schain": {
    "name": "skalenetwork/schain",
    "version": "3.14.0-develop.0",
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


def ensure_in_maintenance(skale, node_id):
    if skale.nodes.get_node_status(node_id) == NodeStatus.ACTIVE:
        skale.nodes.set_node_in_maintenance(node_id)


def ensure_not_in_maintenance(skale, node_id):
    if skale.nodes.get_node_status(node_id) == NodeStatus.IN_MAINTENANCE:
        skale.nodes.remove_node_from_in_maintenance(node_id)


def generate_sgx_wallets(skale, n_of_keys):
    logger.info(f'Generating {n_of_keys} test wallets')
    return [
        SgxWallet(
            SGX_SERVER_URL,
            skale.web3,
            path_to_cert=SGX_CERTIFICATES_FOLDER
        )
        for _ in range(n_of_keys)
    ]


def link_node_address(skale, wallet):
    validator_id = skale.validator_service.validator_id_by_address(
        skale.wallet.address)
    main_wallet = skale.wallet
    skale.wallet = wallet
    signature = skale.validator_service.get_link_node_signature(
        validator_id=validator_id
    )
    skale.wallet = main_wallet
    skale.validator_service.link_node_address(
        node_address=wallet.address,
        signature=signature
    )


def transfer_eth_to_wallets(skale, wallets):
    logger.info(
        'Transfering %d ETH to %d test wallets',
        TEST_ETH_AMOUNT, len(wallets)
    )
    for wallet in wallets:
        send_ether(skale.web3, skale.wallet, wallet.address, TEST_ETH_AMOUNT)


def link_addresses_to_validator(skale, wallets):
    logger.info('Linking addresses to validator')
    for wallet in wallets:
        link_node_address(skale, wallet)


@dataclass
class TestNodeConfig:
    id: int
    ip: str
    name: str


def register_node(skale):
    ip, public_ip, port, name = generate_random_node_data()
    port = 10000
    skale.manager.create_node(
        ip=ip,
        port=port,
        name=name,
        public_ip=public_ip,
        domain_name=DEFAULT_DOMAIN_NAME
    )
    node_id = skale.nodes.node_name_to_index(name)
    logger.info('Registered node %s, ID: %d', name, node_id)
    node_config = TestNodeConfig(id=node_id, ip=ip, name=name)
    return Node(skale, config=node_config)


def register_nodes(skale_instances):
    nodes = [
        register_node(sk)
        for sk in skale_instances
    ]
    return nodes


def sgx_wallets(skale, amount=1):
    wallets = generate_sgx_wallets(skale, amount)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    return wallets


def skale_sgx_instances(skale, sgx_wallets):
    return [
        init_skale_from_wallet(w)
        for w in sgx_wallets
    ]


def remove_schain(skale, schain_name):
    print('Cleanup nodes and schains')
    if schain_name is not None:
        if skale.schains_internal.is_schain_exist(schain_name):
            skale.manager.delete_schain(schain_name)


def remove_nodes(skale, nodes):
    for node_id in nodes:
        ensure_not_in_maintenance(skale, node_id)
        if skale.nodes.get_node_status(node_id) == NodeStatus.ACTIVE:
            skale.nodes.init_exit(node_id)
            skale.manager.node_exit(node_id)


def create_nodes(skale, amount=1):
    wallets = sgx_wallets(skale, amount=amount)
    skales = skale_sgx_instances(skale, wallets)
    return register_nodes(skales)


def create_schains(skale, amount=1):
    names = [generate_random_name(len=10) for _ in range(amount)]
    for name in names:
        create_schain(skale, name)
    return names


def create_schain(
    skale: Skale,
    name: str,
    lifetime_seconds: int = DEFAULT_SCHAIN_LIFETIME,
    type_of_nodes: int = TEST2_TYPE,
    srw_fund: int = TEST_SRW_FUND_VALUE
) -> None:
    _ = skale.schains.get_schain_price(
        type_of_nodes, lifetime_seconds
    )
    skale.schains.grant_role(skale.schains.schain_creator_role(),
                             skale.wallet.address)
    skale.schains.add_schain_by_foundation(
        lifetime_seconds,
        type_of_nodes,
        0,
        name,
        value=srw_fund
    )
