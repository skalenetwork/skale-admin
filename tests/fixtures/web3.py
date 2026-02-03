import pathlib
import shutil

import pytest
from eth_typing import HexStr
from skale import FairManager, SkaleIma, SkaleManager
from skale.types.schain import SchainHash
from skale.utils.account_tools import generate_account, send_eth
from skale.utils.cache import RedisCacheConfig
from skale.utils.contracts_provision.fake_multisig_contract import deploy_fake_multisig_contract
from skale.utils.contracts_provision.main import (
    add_test2_schain_type,
    add_test4_schain_type,
    add_test_permissions,
    cleanup_nodes,
    cleanup_nodes_schains,
    create_nodes,
    create_schain,
    create_validator,
    enable_validator,
    link_nodes_to_validator,
    set_test_msr,
    validator_exist,
)
from skale.utils.helper import schain_name_to_hash
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet

from core.manager_cache import ManagerCache
from core.node_config import NodeConfig
from tests.fixtures.settings import TestingSettings
from tools.constants import SGX_CERTIFICATES_FOLDER
from tools.constants.db import REDIS_URI
from tools.constants.web3 import CACHE_TTL_POLICY
from tools.resources import rs
from tools.settings import FairBaseSettings, SkaleBaseSettings, SkaleSettings

ETH_AMOUNT_PER_NODE = 1
NUMBER_OF_NODES = 2


@pytest.fixture
def number_of_nodes() -> int:
    """Returns the number of nodes to be used in tests."""
    return NUMBER_OF_NODES


@pytest.fixture
def eth_per_node() -> int:
    """Returns the number of nodes to be used in tests."""
    return ETH_AMOUNT_PER_NODE


@pytest.fixture(scope='session')
def endpoint(st: SkaleBaseSettings) -> str:
    return str(st.endpoint)


@pytest.fixture(scope='session')
def manager_contracts(st: SkaleBaseSettings) -> str:
    return st.contracts.manager


@pytest.fixture(scope='session')
def fair_contracts(st: FairBaseSettings) -> str:
    return st.contracts.fair


@pytest.fixture(scope='session')
def ima_contracts(st: SkaleSettings) -> str:
    return st.contracts.ima


@pytest.fixture(scope='session')
def private_key(st: TestingSettings) -> HexStr:
    return st.eth_private_key


@pytest.fixture(scope='session')
def redis_cache_config() -> RedisCacheConfig:
    return RedisCacheConfig(
        REDIS_URI,
        method_ttl_policy=CACHE_TTL_POLICY,
    )


@pytest.fixture(scope='session')
def web3(endpoint, redis_cache_config):
    return init_web3(endpoint, cache_config=redis_cache_config)


@pytest.fixture(scope='session')
def wallet(web3, private_key):
    return Web3Wallet(private_key, web3)


@pytest.fixture(scope='session')
def sgx_cert_folder():
    try:
        shutil.rmtree(SGX_CERTIFICATES_FOLDER, ignore_errors=True)
        pathlib.Path(SGX_CERTIFICATES_FOLDER).mkdir(parents=True, exist_ok=True)
        yield
    finally:
        shutil.rmtree(SGX_CERTIFICATES_FOLDER, ignore_errors=True)


@pytest.fixture(scope='session')
def skale(endpoint, manager_contracts, wallet, sgx_cert_folder):
    skale_obj = SkaleManager(
        endpoint,
        manager_contracts,
        wallet,
        redis_cache_config=RedisCacheConfig(
            REDIS_URI,
            method_ttl_policy={
                'eth_call': 0,
                'eth_getCode': 10000,
                'eth_getStorageAt': 10000,
                'eth_chainId': 10000,
                'eth_getBlockByNumber': 10000,
                'eth_gasPrice': 10000,
                'web3_clientVersion': 10000,
            },
        ),
    )
    add_test_permissions(skale_obj)
    add_test2_schain_type(skale_obj)
    add_test4_schain_type(skale_obj)
    if skale_obj.constants_holder.get_launch_timestamp() != 0:
        skale_obj.constants_holder.set_launch_timestamp(0)
    deploy_fake_multisig_contract(skale_obj.web3, skale_obj.wallet)
    return skale_obj


@pytest.fixture(scope='session')
def skale_ima(endpoint, ima_contracts, wallet, sgx_cert_folder):
    return SkaleIma(endpoint, ima_contracts, wallet)


@pytest.fixture(scope='session')
def fair(endpoint, fair_contracts, wallet, sgx_cert_folder):
    return FairManager(endpoint, fair_contracts, wallet)


# skale


@pytest.fixture
def schain_on_contracts(skale, nodes, _schain_name):
    try:
        yield create_schain(
            skale,
            schain_type=1,  # test2 should have 1 index
            schain_name=_schain_name,
        )
    finally:
        cleanup_nodes_schains(skale)


@pytest.fixture
def schain_hash_on_contracts(schain_on_contracts) -> SchainHash:
    return schain_name_to_hash(schain_on_contracts)


@pytest.fixture(scope='session')
def validator(skale):
    set_test_msr(skale, 0)
    if not validator_exist(skale):
        create_validator(skale)
    validator_id = skale.validator_service.validator_id_by_address(skale.wallet.address)
    if not skale.validator_service.get(validator_id)['trusted']:
        enable_validator(skale, validator_id)


@pytest.fixture
def node_wallets(skale, number_of_nodes, eth_per_node) -> list[Web3Wallet]:
    wallets = []
    for _ in range(number_of_nodes):
        account = generate_account(skale.web3)
        wallet = Web3Wallet(account['private_key'], skale.web3)
        send_eth(
            web3=skale.web3,
            wallet=skale.wallet,
            receiver_address=wallet.address,
            amount=eth_per_node,
        )
        wallets.append(wallet)
    return wallets


@pytest.fixture
def node_skales(endpoint, manager_contracts, node_wallets):
    return [SkaleManager(endpoint, manager_contracts, wallet) for wallet in node_wallets]


@pytest.fixture
@pytest.mark.parametrize('number_of_nodes', [1])
def new_node_wallet(node_wallets) -> Web3Wallet:
    return node_wallets[0]


@pytest.fixture
def nodes(skale, node_skales, validator):
    cleanup_nodes(skale, skale.nodes.active_node_ids())
    link_nodes_to_validator(skale, validator, node_skales)
    ids = create_nodes(node_skales)
    try:
        yield ids
    finally:
        cleanup_nodes(skale, ids)


@pytest.fixture
def manager_cache(skale, node_config: NodeConfig) -> ManagerCache:
    return ManagerCache(rs, skale, node_config.id)


@pytest.fixture
def clear_manager_cache(skale, node_config: NodeConfig) -> ManagerCache:
    mcache = ManagerCache(rs, skale, node_config.id)
    mcache.clear_all_fields()
    return mcache
