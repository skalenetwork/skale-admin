import pathlib
import shutil
from typing import cast

import pytest
from eth_typing import HexStr
from skale import FairManager, SkaleIma, SkaleManager
from skale.utils.account_tools import generate_account, send_eth
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
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet

from tests.utils import ETH_PRIVATE_KEY
from tools.configs.ima import IMA_CONTRACTS
from tools.configs.sgx import SGX_CERTIFICATES_FOLDER
from tools.configs.web3 import ENDPOINT, FAIR_CONTRACTS, MANAGER_CONTRACTS

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
def endpoint() -> str:
    if not ENDPOINT:
        raise ValueError('Set ENDPOINT environment variable to use endpoint fixture')
    return ENDPOINT


@pytest.fixture(scope='session')
def manager_contracts() -> str:
    if not MANAGER_CONTRACTS:
        raise ValueError(
            'Set MANAGER_CONTRACTS environment variable to use manager_contracts fixture'
        )
    return MANAGER_CONTRACTS


@pytest.fixture(scope='session')
def ima_contracts() -> str:
    if not IMA_CONTRACTS:
        raise ValueError('Set IMA_CONTRACTS environment variable to use ima_contracts fixture')
    return IMA_CONTRACTS


@pytest.fixture(scope='session')
def fair_contracts() -> str:
    if not FAIR_CONTRACTS:
        raise ValueError('Set FAIR_CONTRACTS environment variable to use fair_contracts fixture')
    return FAIR_CONTRACTS


@pytest.fixture(scope='session')
def private_key() -> HexStr:
    if not ETH_PRIVATE_KEY:
        raise ValueError('Set ETH_PRIVATE_KEY environment variable to use private_key fixture')
    return cast(HexStr, ETH_PRIVATE_KEY)


@pytest.fixture(scope='session')
def web3(endpoint):
    return init_web3(endpoint)


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
    skale_obj = SkaleManager(endpoint, manager_contracts, wallet)
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


# fair
