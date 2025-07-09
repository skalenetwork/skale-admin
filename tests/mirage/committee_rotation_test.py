import pytest
from skale import MirageManager, SkaleManager

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
from tools.configs.web3 import ENDPOINT, MANAGER_CONTRACTS
from tools.helper import read_json, run_cmd

N_OF_NODES = 2


@pytest.fixture
def schain_creation_data():
    _, lifetime_seconds, name = generate_random_schain_data()
    return name, lifetime_seconds


@pytest.fixture(scope='class')
def sgx_wallets(skale):
    wallets = generate_sgx_wallets(skale, N_OF_NODES)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    return wallets


@pytest.fixture(scope='class')
def skale_sgx_instances(skale, endpoint, manager_contracts, sgx_wallets):
    return [SkaleManager(endpoint, manager_contracts, w) for w in sgx_wallets]


@pytest.fixture(scope='class')
def other_maintenance(skale):
    nodes = skale.nodes.get_active_node_ids()
    for nid in nodes:
        skale.nodes.set_node_in_maintenance(nid)
    yield
    for nid in nodes:
        skale.nodes.remove_node_from_in_maintenance(nid)


@pytest.fixture(scope='class')
def nodes(skale, validator, skale_sgx_instances, other_maintenance):
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
    schain_name, _ = schain_creation_data
    assert not is_last_dkg_finished(skale, schain_name)
    nodes.sort(key=lambda x: x['node_id'])
    runners = get_dkg_runners(skale, skale_sgx_instances, schain_name, nodes)
    results = exec_dkg_runners(runners)
    assert len(results) == N_OF_NODES
    assert is_last_dkg_finished(skale, schain_name)


@pytest.fixture
def mirage_contracts(schain_creation_data):
    chain_name = schain_creation_data[0]

    env = {
        'MAINNET_ENDPOINT': ENDPOINT,
        'TARGET': MANAGER_CONTRACTS,
        'PRIVATE_KEY': ETH_PRIVATE_KEY,
        'DOCKER_NETWORK': 'host',
        'CHAIN_NAME': chain_name,
    }
    run_cmd(['helper-scripts/deploy_mirage.sh'], env=env)

    return read_json('helper-scripts/contracts_data/mirage.json')['Committee']


@pytest.fixture
def mirage(skale_dkg, mirage_contracts, skale):
    """Generate all mirage preconditions:
    1. Deploy skale manager contracts
    2. Create 2 nodes
    3. Create a skale chain
    4. Deploy mirage manager
    """
    return MirageManager(ENDPOINT, mirage_contracts, skale.wallet)


def test_committee_rotation(mirage):
    assert mirage.nodes.get_active_node_ids() == []
    assert True
