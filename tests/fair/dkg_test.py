import functools
import logging
import time
from contextlib import contextmanager
from unittest import mock

import pytest
from skale import FairManager, SkaleManager
from skale.types.dkg import Status
from skale.types.node import NodeId, NodeStatus
from skale.utils.account_tools import send_eth
from skale.wallets.web3_wallet import generate_wallet

from core.config.schain.directory import init_schain_config_dir
from core.dkg.fair.main import get_dkg_client, run_dkg
from core.dkg.structures import DKGResult
from core.dkg.utils import DkgError
from tests.dkg_test.main_test import (
    DKG_TIMEOUT,
    DKGRunType,
    DKGStatus,
    DKGStep,
    cleanup_schain_config,
    create_schain,
    exec_dkg_runners,
    generate_random_node_data,
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

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def no_zero_node(validator, skale, manager_contracts, endpoint):
    if skale.nodes.nodes_number() == 0 or skale.nodes.get(0)['status'] != NodeStatus.LEFT:
        wallet = generate_wallet(skale.web3)
        link_addresses_to_validator(skale, [wallet])
        transfer_eth_to_wallets(skale, [wallet])
        register_nodes([SkaleManager(endpoint, manager_contracts, wallet)])
        if skale.nodes.get(0)['status'] != NodeStatus.ACTIVE:
            skale.manager.remove_node_from_in_maintenance(0)
        skale.nodes.init_exit(0)
        skale.manager.node_exit(0)


@pytest.fixture
def dkg_timeout(skale):
    skale.constants_holder.set_complaint_timelimit(DKG_TIMEOUT)


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


@contextmanager
def fair_dkg_test_client(
    skale: FairManager,
    node_id: int,
    sgx_key_name: str,
    rotation_id: int,
    chain_name: str,
    run_type: DKGRunType = DKGRunType.NORMAL,
):
    dkg_client = get_dkg_client(node_id, skale, sgx_key_name, rotation_id, chain_name)
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


def run_fair_dkg(
    skale: FairManager,
    index: int,
    node_id: int,
    chain_name: str,
    runs: tuple[DKGRunType] = (DKGRunType.NORMAL,),
) -> DKGResult:
    init_schain_config_dir('fair')
    sgx_key_name = skale.wallet._key_name
    committee_id = skale.dkg.get_last_dkg_id()

    timeout = index * 5  # diversify start time for all nodes
    logger.info('Node %d going to sleep %d seconds %s', node_id, timeout, type(runs))
    time.sleep(timeout)
    logger.info('Starting runs %s, %d', runs, len(runs))
    dkg_result = None
    for run_type in runs:
        logger.info('Running %s dkg', run_type)
        with fair_dkg_test_client(
            skale, node_id, sgx_key_name, committee_id, chain_name, run_type
        ) as dkg_client:
            logger.info('ID skale %d', id(dkg_client.skale))
            try:
                dkg_result = run_dkg(skale, dkg_client)
            except Exception:
                logger.exception('DKG run failed')
            else:
                if dkg_result.status == DKGStatus.DONE:
                    logger.info('DKG completed')
                    break
        logger.info('Finished run %s', run_type)

    logger.info('Completed runs %s', runs)
    return dkg_result


def run_node_fair_dkg(
    fair: FairManager,
    index: int,
    node_id: int,
    chain_name: str,
    runs: tuple[DKGRunType] = (DKGRunType.NORMAL,),
):
    init_schain_config_dir('fair')
    # sgx_key_name = fair.wallet._key_name
    # committee_id = fair.dkg.get_last_dkg_id()

    timeout = index * 5  # diversify start time for all nodes
    logger.info('Node %d going to sleep %d seconds %s', node_id, timeout, type(runs))
    time.sleep(timeout)
    logger.info('Starting runs %s, %d', runs, len(runs))
    dkg_result = None
    for run_type in runs:
        logger.info('Running %s dkg', run_type)
        logger.info('ID fair %d', id(fair))
        try:
            dkg_result = run_fair_dkg(fair, index, node_id, chain_name, [run_type])
        except Exception:
            logger.exception('Fair DKG run failed')
        else:
            if dkg_result.status == DKGStatus.DONE:
                logger.info('Fair DKG completed')
                break
        logger.info('Finished run %s', run_type)

    logger.info('Completed runs %s', runs)
    return dkg_result


def get_fair_dkg_runners(fair_sgx_instances, fair_nodes, chain_name):
    runners = []
    for i, (node_fair, node) in enumerate(zip(fair_sgx_instances, fair_nodes)):
        runners.append(functools.partial(run_node_fair_dkg, node_fair, i, node.id, chain_name))
    return runners


class TestDKGFair:
    @pytest.fixture
    def schain_creation_data(self):
        _, lifetime_seconds, name = generate_random_schain_data()
        return name, lifetime_seconds

    @pytest.fixture(scope='class')
    def sgx_wallets(self, skale, no_zero_node):
        wallets = generate_sgx_wallets(skale, N_OF_NODES)
        transfer_eth_to_wallets(skale, wallets)
        link_addresses_to_validator(skale, wallets)
        return wallets

    @pytest.fixture(scope='class')
    def skale_sgx_instances(self, skale, endpoint, manager_contracts, sgx_wallets):
        return [SkaleManager(endpoint, manager_contracts, w) for w in sgx_wallets]

    @pytest.fixture(scope='class')
    def other_maintenance(self, skale):
        nodes = skale.nodes.active_node_ids()
        if N_OF_NODES > len(nodes):
            for i in range(N_OF_NODES, len(nodes)):
                skale.nodes.set_node_in_maintenance(nodes[i])
        try:
            yield
        finally:
            for i in range(N_OF_NODES, len(nodes)):
                skale.nodes.set_node_in_maintenance(nodes[i])

    @pytest.fixture(scope='class')
    def nodes(self, skale, validator, skale_sgx_instances):
        nodes = register_nodes(skale_sgx_instances)
        try:
            yield nodes
        finally:
            nids = [node['node_id'] for node in nodes]
            remove_nodes(skale, nids)

    @pytest.fixture
    def dkg_timeout(self, skale):
        skale.constants_holder.set_complaint_timelimit(DKG_TIMEOUT)

    @pytest.fixture
    def schain(self, schain_creation_data, skale, nodes):
        schain_name, lifetime = schain_creation_data
        create_schain(skale, schain_name, lifetime)
        try:
            yield schain_name
        finally:
            remove_schain(skale, schain_name)
            cleanup_schain_config(schain_name)

    @pytest.fixture
    def fair_contracts(self, schain_creation_data, skale_dkg, endpoint, manager_contracts):
        chain_name = schain_creation_data[0]

        env = {
            'MAINNET_ENDPOINT': endpoint,
            'TARGET': manager_contracts,
            'PRIVATE_KEY': ETH_PRIVATE_KEY,
            'DOCKER_NETWORK': 'host',
            'CHAIN_NAME': chain_name,
        }
        run_cmd(['helper-scripts/deploy_fair.sh'], env=env)

        return read_json('helper-scripts/contracts_data/fair.json')['Committee']

    @pytest.fixture
    def fair(self, skale_dkg, fair_contracts, endpoint, skale):
        """Generate all fair preconditions:
        1. Deploy skale manager contracts
        2. Create 2 nodes
        3. Create a skale chain
        4. Deploy fair manager
        """
        # using the same endpoint as for skale manager
        return FairManager(endpoint, fair_contracts, skale.wallet)

    @pytest.fixture
    def fair_sgx_instances(self, sgx_wallets, fair_contracts, endpoint):
        return [FairManager(endpoint, fair_contracts, w) for w in sgx_wallets]

    @pytest.fixture
    def new_wallet(self, fair):
        wallet = generate_sgx_wallets(fair, 1)[0]
        print('Address', fair.wallet.address, fair.web3.eth.get_balance(fair.wallet.address))
        send_eth(web3=fair.web3, wallet=fair.wallet, receiver_address=wallet.address, amount=0.1)
        return wallet

    @pytest.fixture
    def new_fair_instance(self, new_wallet, fair_contracts, endpoint):
        return FairManager(endpoint, fair_contracts, new_wallet)

    @pytest.fixture
    def fair_new_node(self, fair, new_fair_instance):
        ip, _, port, _ = generate_random_node_data()
        self_stake_requirement = new_fair_instance.staking.self_stake_requirement()
        new_fair_instance.nodes.register_active(ip, port, value=self_stake_requirement)
        return new_fair_instance.nodes.get_by_address(new_fair_instance.wallet.address)

    @pytest.fixture
    def fair_nodes(self, fair, nodes):
        return [fair.nodes.get(node['node_id']) for node in nodes]

    def test_dkg_procedure_normal(
        self, skale, schain_creation_data, fair_sgx_instances, fair_nodes, schain, fair
    ):
        fair.dkg.generate([NodeId(node.id) for node in fair_nodes])
        new_dkg_id = fair.dkg.get_last_dkg_id()
        schain_name, _ = schain_creation_data
        assert fair.dkg.get_round(new_dkg_id).status == Status.BROADCAST
        fair_nodes.sort(key=lambda x: x.id)
        runners = get_fair_dkg_runners(fair_sgx_instances, fair_nodes, 'fair')
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES

        for node_data, result in zip(fair_nodes, results):
            assert result.status.is_done()
            assert result.step == DKGStep.KEY_GENERATION
            keys_data = result.keys_data
            assert keys_data is not None
        assert fair.dkg.get_round(new_dkg_id).status == Status.SUCCESS

        regular_dkg_keys_data = sorted([r.keys_data for r in results], key=lambda d: d['n'])
        time.sleep(3)
        # Rerun dkg to emulate restoring keys

        fair_nodes.sort(key=lambda x: x.id)
        runners = get_fair_dkg_runners(fair_sgx_instances, fair_nodes, 'fair')
        results = exec_dkg_runners(runners)
        assert all([r.status.is_done() for r in results])
        assert fair.dkg.get_round(new_dkg_id).status == Status.SUCCESS

        restore_dkg_keys_data = sorted([r.keys_data for r in results], key=lambda d: d['n'])
        assert regular_dkg_keys_data == restore_dkg_keys_data

    # def test_committee_rotation(
    # self, fair, fair_nodes, fair_sgx_instances, schain_creation_data):
    #     fair.dkg.generate([node.id for node in fair_nodes])
    #     chain_name, _ = schain_creation_data
    #     runners = get_fair_dkg_runners(fair_nodes, fair_sgx_instances, chain_name)
    #     exec_dkg_runners(runners)
