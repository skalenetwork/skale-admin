import pytest
from skale import MirageManager, SkaleManager
from skale.utils.exceptions import InvalidNodeIdError
from skale.wallets.web3_wallet import generate_wallet
from web3.exceptions import Web3RPCError

from tests.dkg_test.main_test import (
    DKG_TIMEOUT,
    cleanup_schain_config,
    create_schain,
    exec_dkg_runners,
    generate_random_schain_data,
    generate_sgx_wallets,
    get_dkg_runners,
    is_last_dkg_finished,
    link_addresses_to_validator,
    register_nodes,
    remove_nodes,
    remove_schain,
    transfer_eth_to_wallets,
)
from tests.utils import ETH_PRIVATE_KEY
from tools.helper import read_json, run_cmd

N_OF_NODES = 2


@pytest.fixture(scope='session')
def no_zero_node(validator, skale, manager_contracts, endpoint):
    try:
        skale.nodes.get(0)
    except (Web3RPCError, InvalidNodeIdError):
        wallet = generate_wallet(skale.web3)
        link_addresses_to_validator(skale, [wallet])
        transfer_eth_to_wallets(skale, [wallet])
        register_nodes([SkaleManager(endpoint, manager_contracts, wallet)])
        skale.manager.node_exit(0)


@pytest.fixture
def schain_creation_data():
    _, lifetime_seconds, name = generate_random_schain_data()
    return name, lifetime_seconds


@pytest.fixture(scope='class')
def sgx_wallets(skale, no_zero_node):
    wallets = generate_sgx_wallets(skale, N_OF_NODES)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    return wallets


@pytest.fixture(scope='class')
def skale_sgx_instances(skale, endpoint, manager_contracts, sgx_wallets):
    return [SkaleManager(endpoint, manager_contracts, w) for w in sgx_wallets]


@pytest.fixture(scope='class')
def other_maintenance(self, skale):
    nodes = skale.nodes.get_active_node_ids()
    if N_OF_NODES > len(nodes):
        for i in range(N_OF_NODES, len(nodes)):
            skale.nodes.set_node_in_maintenance(nodes[i])
    try:
        yield
    finally:
        for i in range(N_OF_NODES, len(nodes)):
            skale.nodes.set_node_in_maintenance(nodes[i])


@pytest.fixture(scope='class')
def nodes(skale, validator, skale_sgx_instances):
    nodes = register_nodes(skale_sgx_instances)
    try:
        yield nodes
    finally:
        nids = [node['node_id'] for node in nodes]
        remove_nodes(skale, nids)


@pytest.fixture
def dkg_timeout(skale):
    skale.constants_holder.set_complaint_timelimit(DKG_TIMEOUT)


@pytest.fixture
def schain(schain_creation_data, skale, nodes):
    schain_name, lifetime = schain_creation_data
    create_schain(skale, schain_name, lifetime)
    try:
        yield schain_name
    finally:
        remove_schain(skale, schain_name)
        cleanup_schain_config(schain_name)


@pytest.fixture
def skale_dkg(skale, schain, schain_creation_data, nodes, skale_sgx_instances, dkg_timeout):
    sgx_instances = skale_sgx_instances
    schain_name, _ = schain_creation_data
    assert not is_last_dkg_finished(skale, schain_name)
    nodes.sort(key=lambda x: x['node_id'])
    runners = get_dkg_runners(skale, sgx_instances, schain_name, nodes)
    results = exec_dkg_runners(runners)
    assert len(results) == N_OF_NODES
    assert is_last_dkg_finished(skale, schain_name)


@pytest.fixture
def mirage_contracts(schain_creation_data, endpoint, manager_contracts):
    chain_name = schain_creation_data[0]

    env = {
        'MAINNET_ENDPOINT': endpoint,
        'TARGET': manager_contracts,
        'PRIVATE_KEY': ETH_PRIVATE_KEY,
        'DOCKER_NETWORK': 'host',
        'CHAIN_NAME': chain_name,
    }
    run_cmd(['helper-scripts/deploy_mirage.sh'], env=env)

    return read_json('helper-scripts/contracts_data/mirage.json')['Committee']


@pytest.fixture
def mirage(skale_dkg, mirage_contracts, endpoint, skale):
    """Generate all mirage preconditions:
    1. Deploy skale manager contracts
    2. Create 2 nodes
    3. Create a skale chain
    4. Deploy mirage manager
    """
    # using the same endpoint as for skale manager
    return MirageManager(endpoint, mirage_contracts, skale.wallet)


def test_committee_rotation(mirage):
    assert mirage.nodes.get_active_node_ids() == []
    assert True
