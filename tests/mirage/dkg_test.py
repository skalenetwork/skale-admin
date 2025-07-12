import functools
import logging
import time
from contextlib import contextmanager
from unittest import mock

import pytest
from skale import MirageManager, SkaleManager
from skale.types.dkg import Status
from skale.types.node import NodeStatus
from skale.types.schain import SchainName
from skale.utils.account_tools import send_eth
from skale.wallets.web3_wallet import generate_wallet

from core.config.schain.directory import init_schain_config_dir
from core.dkg.mirage.main import get_dkg_client, run_dkg
from core.dkg.structures import DKGResult
from tests.dkg_test.main_test import (
    DKG_TIMEOUT,
    DKGRunType,
    DKGStatus,
    DKGStep,
    generate_random_node_data,
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
from core.dkg.utils import DkgError
from tests.utils import ETH_PRIVATE_KEY
from tools.helper import read_json, run_cmd

N_OF_NODES = 2

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def no_zero_node(validator, skale, manager_contracts, endpoint):
    if skale.nodes.get_nodes_number() == 0 or skale.nodes.get(0)['status'] != NodeStatus.LEFT:
        wallet = generate_wallet(skale.web3)
        link_addresses_to_validator(skale, [wallet])
        transfer_eth_to_wallets(skale, [wallet])
        register_nodes([SkaleManager(endpoint, manager_contracts, wallet)])
        if skale.nodes.get(0)['status'] != NodeStatus.ACTIVE:
            skale.manager.remove_node_from_in_maintenance(0)
        skale.nodes.init_exit(0)
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
def mirage_contracts(schain_creation_data, skale_dkg, endpoint, manager_contracts):
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


@pytest.fixture
def mirage_sgx_instances(sgx_wallets, mirage_contracts, endpoint):
    return [MirageManager(endpoint, mirage_contracts, w) for w in sgx_wallets]


@contextmanager
def mirage_dkg_test_client(skale: MirageManager,
    node_id: int,
    sgx_key_name: str,
    rotation_id: int,
    run_type: DKGRunType = DKGRunType.NORMAL
):
    dkg_client = get_dkg_client(node_id, skale, sgx_key_name, rotation_id)
    method, original = None, None
    if run_type == DKGRunType.BROADCAST_FAILED:
        effect = DkgError('Broadcast failed on purpose')
        method, original = 'broadcast', dkg_client.skale.dkg.broadcast
        dkg_client.skale.dkg.broadcast = mock.Mock(side_effect=effect)
    if run_type == DKGRunType.NO_BROADCAST:
        method, original = 'broadcast', dkg_client.skale.dkg.broadcast
        dkg_client.skale.dkg.broadcast = mock.Mock()
    elif run_type == DKGRunType.ALRIGHT_FAILED:
        effect = DkgError('Alright failed on purpose')
        method, original = 'alright', dkg_client.skale.dkg.alright
        dkg_client.skale.dkg.alright = mock.Mock(side_effect=effect)

    try:
        yield dkg_client
    finally:
        if method:
            setattr(dkg_client.skale.dkg, method, original)


def run_mirage_dkg(skale: MirageManager,
    index: int,
    node_id: int,
    runs: tuple[DKGRunType] = (DKGRunType.NORMAL,),
) -> DKGResult:
    init_schain_config_dir("mirage")
    sgx_key_name = skale.wallet._key_name
    committee_id = skale.dkg.get_last_dkg_id()

    timeout = index * 5  # diversify start time for all nodes
    logger.info('Node %d going to sleep %d seconds %s', node_id, timeout, type(runs))
    time.sleep(timeout)
    logger.info('Starting runs %s, %d', runs, len(runs))
    dkg_result = None
    for run_type in runs:
        logger.info('Running %s dkg', run_type)
        with mirage_dkg_test_client(
            skale, node_id, sgx_key_name, committee_id, run_type
        ) as dkg_client:
            logger.info('ID skale %d', id(dkg_client.skale))
            try:
                dkg_result = run_dkg( skale, dkg_client )
            except Exception:
                logger.exception('DKG run failed')
            else:
                if dkg_result.status == DKGStatus.DONE:
                    logger.info('DKG completed')
                    break
        logger.info('Finished run %s', run_type)

    logger.info('Completed runs %s', runs)
    return dkg_result


def run_node_mirage_dkg(
    mirage: MirageManager,
    index: int,
    node_id: int,
    runs: tuple[DKGRunType] = (DKGRunType.NORMAL,),
):
    init_schain_config_dir("mirage")
    sgx_key_name = mirage.wallet._key_name
    committee_id = mirage.committee.get_active_committee_index()

    timeout = index * 5  # diversify start time for all nodes
    logger.info('Node %d going to sleep %d seconds %s', node_id, timeout, type(runs))
    time.sleep(timeout)
    logger.info('Starting runs %s, %d', runs, len(runs))
    dkg_result = None
    for run_type in runs:
        logger.info('Running %s dkg', run_type)
        with mirage_dkg_test_client() as dkg_client:
            logger.info('ID mirage %d', id(dkg_client.mirage))
            try:
                dkg_result = run_mirage_dkg(
                    mirage, dkg_client, node_id, sgx_key_name, committee_id
                )
            except Exception:
                logger.exception('Mirage DKG run failed')
            else:
                if dkg_result.status == DKGStatus.DONE:
                    logger.info('Mirage DKG completed')
                    break
        logger.info('Finished run %s', run_type)

    logger.info('Completed runs %s', runs)
    return dkg_result


def get_mirage_dkg_runners(nodes, mirage_sgx_instances):
    runners = []
    for i, (node_mirage, node_data) in enumerate(zip(mirage_sgx_instances, nodes)):
        runners.append(
            functools.partial(
                run_node_mirage_dkg, node_mirage, i, node_data['node_id']
            )
        )
    return runners

@pytest.fixture
def mirage_nodes(mirage, nodes):
    return [
        mirage.nodes.get(node['node_id'])
        for node in nodes
    ]


@pytest.fixture
def new_wallet(mirage):
    wallet = generate_sgx_wallets(mirage, 1)
    send_eth(
        web3=mirage.web3,
        wallet=mirage.wallet,
        receiver_address=wallet.address,
        amount=mirage.web3.to_wei(0.1, 'ether'),
    )
    return wallet


@pytest.fixture
def new_mirage_instance(new_wallet, mirage_contracts, endpoint):
    return MirageManager(endpoint, mirage_contracts)


@pytest.fixture
def mirage_new_node(mirage, new_mirage_instance):
    ip, _, port, _ = generate_random_node_data()
    new_mirage_instance.node.register_active(ip, port)
    return new_mirage_instance.node.get_by_address(new_mirage_instance.wallet.address)



def test_committee_rotation(mirage, mirage_nodes, mirage_sgx_instances, mirage_new_node):
    pass
    # mirage.committee.select()
    # chain_name = mirage.committee.chain_name
    # runners = get_mirage_dkg_runners(nodes, mirage_sgx_instances, chain_name)
    # exec_dkg_runners(runners)

def test_dkg_procedure_normal(
        self, skale, schain_creation_data, skale_sgx_instances, nodes, dkg_timeout, schain
    ):
        schain_name, _ = schain_creation_data
        assert skale.dkg.get_round(skale.dkg.get_last_dkg_id()).status == Status.BROADCAST
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_mirage_dkg_runners(skale, skale_sgx_instances, nodes)
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES

        for node_data, result in zip(nodes, results):
            assert result.status.is_done()
            assert result.step == DKGStep.KEY_GENERATION
            keys_data = result.keys_data
            assert keys_data is not None
        assert skale.dkg.get_round(skale.dkg.get_last_dkg_id()).status == Status.SUCCESS

        regular_dkg_keys_data = sorted([r.keys_data for r in results], key=lambda d: d['n'])
        time.sleep(3)
        # Rerun dkg to emulate restoring keys

        nodes.sort(key=lambda x: x['node_id'])
        runners = get_mirage_dkg_runners(skale, skale_sgx_instances, nodes)
        results = exec_dkg_runners(runners)
        assert all([r.status.is_done() for r in results])
        assert skale.dkg.get_round(skale.dkg.get_last_dkg_id()).status == Status.SUCCESS

        restore_dkg_keys_data = sorted([r.keys_data for r in results], key=lambda d: d['n'])
        assert regular_dkg_keys_data == restore_dkg_keys_data