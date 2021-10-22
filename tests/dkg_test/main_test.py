"""
Test for dkg procedure using SGX keys
"""
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor as Executor

import pytest
import warnings
from skale import Skale
from skale.utils.account_tools import send_ether
from skale.wallets import SgxWallet
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.schains.cleaner import remove_schain_container
# from core.schains.config.generator import generate_schain_config_with_skale
from core.schains.dkg import is_last_dkg_finished, safe_run_dkg
from core.schains.helper import init_schain_dir
from tests.conftest import skale as skale_fixture
from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import (
    generate_random_node_data,
    generate_random_schain_data,
    init_skale_from_wallet,
    init_web3_skale
)
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.bls.dkg_utils import init_dkg_client, generate_bls_keys
from tools.bls.dkg_client import generate_bls_key_name
# from tools.logger import init_logger, Formatter

warnings.filterwarnings("ignore")

MAX_WORKERS = 5
TEST_SRW_FUND_VALUE = 3000000000000000000

owner_skale = init_web3_skale()

log_format = '[%(asctime)s][%(levelname)s] - %(threadName)s - %(name)s:%(lineno)d - %(message)s'  # noqa

# init_logger(Formatter, log_format)

logger = logging.getLogger(__name__)


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
        signature=signature,
        wait_for=True
    )


def transfer_eth_to_wallets(skale, wallets):
    logger.info(f'Transfering {TEST_ETH_AMOUNT} ETH to {len(wallets)} test wallets')
    for wallet in wallets:
        send_ether(skale.web3, skale.wallet, wallet.address, TEST_ETH_AMOUNT)


def link_addresses_to_validator(skale, wallets):
    logger.info('Linking addresses to validator')
    for wallet in wallets:
        link_node_address(skale, wallet)


def register_node(skale):
    ip, public_ip, port, name = generate_random_node_data()
    port = 10000
    skale.manager.create_node(
        ip=ip,
        port=port,
        name=name,
        public_ip=public_ip,
        domain_name=DEFAULT_DOMAIN_NAME,
        wait_for=True
    )
    node_id = skale.nodes.node_name_to_index(name)
    logger.info(f'Registered node {name}, ID: {node_id}')
    return {
        'node': skale.nodes.get_by_name(name),
        'node_id': node_id,
        'wallet': skale.wallet
    }


@pytest.fixture
def other_maintenance(skale):
    nodes = skale.nodes.get_active_node_ids()
    for nid in nodes:
        skale.nodes.set_node_in_maintenance(nid)
    yield
    for nid in nodes:
        skale.nodes.remove_node_from_in_maintenance(nid)


def register_nodes(skale_instances):
    nodes = [
        register_node(sk)
        for sk in skale_instances
    ]
    return nodes


def check_keys(data, expected_keys):
    assert all(key in data for key in expected_keys)


def check_node_ports(info):
    base_port = info['basePort']
    assert isinstance(base_port, int)
    assert info['wsRpcPort'] == base_port + 2
    assert info['wssRpcPort'] == base_port + 7
    assert info['httpRpcPort'] == base_port + 3
    assert info['httpsRpcPort'] == base_port + 8


def check_node_info(node_data, info):
    keys = ['nodeID', 'nodeName', 'basePort', 'httpRpcPort', 'httpsRpcPort',
            'wsRpcPort', 'wssRpcPort', 'bindIP', 'logLevel', 'logLevelConfig',
            'imaMessageProxySChain', 'imaMessageProxyMainNet',
            'rotateAfterBlock', 'ecdsaKeyName', 'wallets', 'minCacheSize',
            'maxCacheSize', 'collectionQueueSize', 'collectionDuration',
            'transactionQueueSize', 'maxOpenLeveldbFiles']
    check_keys(info, keys)
    assert info['nodeID'] == node_data['node_id']
    check_node_ports(info)
    assert info['infoHttpRpcPort'] == info['basePort'] + 9
    assert info['ecdsaKeyName'] == node_data['wallet']._key_name


def check_schain_node_info(node_data, schain_node_info):
    check_keys(schain_node_info,
               ['nodeID', 'nodeName', 'basePort', 'httpRpcPort',
                'httpsRpcPort', 'wsRpcPort', 'wssRpcPort', 'publicKey',
                'blsPublicKey0', 'blsPublicKey1', 'blsPublicKey2',
                'blsPublicKey3', 'owner', 'schainIndex', 'ip', 'publicIP'])
    assert schain_node_info['nodeID'] == node_data['node_id']
    check_node_ports(schain_node_info)


def check_schain_info(nodes, schain_info):
    check_keys(
        schain_info,
        ['schainID', 'schainName', 'schainOwner', 'contractStorageLimit',
         'dbStorageLimit', 'snapshotIntervalSec', 'emptyBlockIntervalMs',
         'maxConsensusStorageBytes', 'maxSkaledLeveldbStorageBytes',
         'maxFileStorageBytes', 'maxReservedStorageBytes',
         'nodes']
    )
    for node_data, schain_node_info in zip(
        nodes, sorted(schain_info['nodes'],
                      key=lambda x: x['nodeID'])):
        check_schain_node_info(node_data, schain_node_info)


def check_config(nodes, node_data, config):
    check_keys(
        config,
        ['sealEngine', 'params', 'genesis', 'accounts', 'skaleConfig']
    )
    check_node_info(node_data, config['skaleConfig']['nodeInfo'])
    check_schain_info(nodes, config['skaleConfig']['sChain'])


def run_dkg_all(skale, skale_sgx_instances, schain_name, nodes):
    futures, results = [], []
    nodes.sort(key=lambda x: x['node_id'])
    with Executor(max_workers=MAX_WORKERS) as executor:
        for i, (node_skale, node_data) in \
                enumerate(zip(skale_sgx_instances, nodes)):
            futures.append(executor.submit(
                run_node_dkg,
                node_skale, schain_name, i, node_data['node_id']
            ))
    for future in futures:
        results.append(future.result())

    bls_public_keys = []
    all_public_keys = []
    for node_data, result in zip(nodes, results):
        assert result.status.is_done()
        keys_data = result.keys_data
        assert keys_data is not None
        bls_public_keys.append(keys_data['public_key'])
        all_public_keys.append(keys_data['bls_public_keys'])
        # check_config(nodes, node_data, result['config'])

    assert len(results) == N_OF_NODES
    gid = skale.schains.name_to_id(schain_name)
    assert skale.dkg.is_last_dkg_successful(gid)
    return bls_public_keys, all_public_keys
    # todo: add some additional checks that dkg is finished successfully


def run_node_dkg(skale, schain_name, index, node_id):
    timeout = index * 5  # diversify start time for all nodes
    logger.info(f'Node {node_id} going to sleep {timeout} seconds')
    time.sleep(timeout)
    sgx_key_name = skale.wallet._key_name

    init_schain_dir(schain_name)
    rotation_id = skale.schains.get_last_rotation_id(schain_name)
    dkg_result = safe_run_dkg(
        skale,
        schain_name,
        node_id,
        sgx_key_name,
        rotation_id
    )
    return dkg_result


def check_fetch_broadcasted_data(
    skale,
    schain_name,
    nodes,
    bls_public_keys,
    all_public_keys
):
    futures, results = [], []
    nodes.sort(key=lambda x: x['node_id'])
    with Executor(max_workers=MAX_WORKERS) as executor:
        for i, node_data in enumerate(nodes):
            opts = {
                'skale': skale,
                'schain_name': schain_name,
                'node_id': node_data['node_id'],
                'wallet': node_data['wallet'],
            }
            futures.append(executor.submit(run_dkg_fetch, opts))
    for future in futures:
        results.append(future.result())

    bls_public_keys_done = []
    all_public_keys_done = []
    for node_data, result in zip(nodes, results):
        assert result is not None
        bls_public_keys_done.append(result['public_key'])
        all_public_keys_done.append(result['bls_public_keys'])

    assert bls_public_keys_done == bls_public_keys
    assert all_public_keys_done == all_public_keys


def run_dkg_fetch(opts):
    skale = skale_fixture()
    skale.wallet = opts['wallet']
    sgx_key_name = skale.wallet._key_name
    schain_name = opts['schain_name']
    node_id = opts['node_id']

    dkg_client = init_dkg_client(node_id, schain_name, skale, sgx_key_name, 0)
    group_index_str = str(int(skale.web3.toHex(dkg_client.group_index)[2:], 16))
    dkg_client.bls_name = generate_bls_key_name(group_index_str, node_id, 2)
    dkg_client.fetch_all_broadcasted_data()
    dkg_results = generate_bls_keys(dkg_client)
    return dkg_results


def create_schain(skale: Skale, name: str, lifetime_seconds: int) -> None:
    _ = skale.schains.get_schain_price(
        TYPE_OF_NODES, lifetime_seconds
    )
    skale.schains.grant_role(skale.schains.schain_creator_role(),
                             skale.wallet.address)
    skale.schains.add_schain_by_foundation(
        lifetime_seconds,
        TYPE_OF_NODES,
        0,
        name,
        wait_for=True,
        value=TEST_SRW_FUND_VALUE
    )


def cleanup_contracts_from_dkg_items(schain_name: str) -> None:
    node_ids = owner_skale.schains_internal.get_node_ids_for_schain(schain_name)
    owner_skale.manager.delete_schain(schain_name)
    for node_id in node_ids:
        owner_skale.manager.node_exit(node_id)


def cleanup_docker_items(schain_name: str) -> None:
    remove_schain_container(schain_name)
    # remove_schain_volume(schain_name)


def cleanup_schain_configs(schain_name: str) -> None:
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    subprocess.run(['rm', '-rf', schain_dir_path])


@pytest.fixture
def cleanup_dkg(schain_creation_data):
    yield
    error = None
    schain_name, _ = schain_creation_data
    # try:
    #     cleanup_contracts_from_dkg_items(schain_name)
    # except Exception as err:
    #     print(f'Cleaning dkg items from contracts failed {err}')
    #     error = err
    try:
        cleanup_docker_items(schain_name)
    except Exception as err:
        print(f'Cleanning schain docker items failed {err}')
        error = err
    try:
        cleanup_schain_configs(schain_name)
    except Exception as err:
        print(f'Cleannuping schain config items failed {err}')
        error = err

    warnings.warn(f'Cleanup dkg failed with {error}')
    # if error:
    #     raise error


@pytest.fixture
def schain_creation_data():
    _, lifetime_seconds, name = generate_random_schain_data()
    return name, lifetime_seconds


@pytest.fixture
def sgx_wallets(skale):
    wallets = generate_sgx_wallets(skale, N_OF_NODES)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    return wallets


@pytest.fixture
def skale_sgx_instances(skale, sgx_wallets):
    return [
        init_skale_from_wallet(w)
        for w in sgx_wallets
    ]


@pytest.fixture
def nodes(skale, skale_sgx_instances, other_maintenance):
    nodes = register_nodes(skale_sgx_instances)
    try:
        yield nodes
    finally:
        return
        nids = [node['node_id'] for node in nodes]
        remove_nodes(skale, nids)


@pytest.fixture
def schain(schain_creation_data, skale, nodes):
    schain_name, lifetime = schain_creation_data
    create_schain(skale, schain_name, lifetime)
    try:
        yield schain_name
    finally:
        remove_schain(skale, schain_name)


def remove_schain(skale, schain_name):
    print('Cleanup nodes and schains')
    if schain_name is not None:
        skale.manager.delete_schain(schain_name, wait_for=True)


def remove_nodes(skale, nodes):
    for node_id in nodes:
        skale.manager.node_exit(node_id, wait_for=True)


def test_dkg(
    skale,
    schain_creation_data,
    skale_sgx_instances,
    nodes,
    schain,
    cleanup_dkg
):
    skale.constants_holder.set_complaint_timelimit(30000000000)
    schain_name, _ = schain_creation_data
    assert not is_last_dkg_finished(skale, schain_name)
    bls_public_keys, all_public_keys = run_dkg_all(
        skale,
        skale_sgx_instances,
        schain_name,
        nodes
    )
    assert is_last_dkg_finished(skale, schain_name)
    # Rerun dkg to regenerate keys
    bls_public_keys, all_public_keys = run_dkg_all(
        skale,
        skale_sgx_instances,
        schain_name,
        nodes
    )
    assert is_last_dkg_finished(skale, schain_name)


@pytest.mark.skip
def test_generate_bls_keys(skale):
    init_dkg_client(skale)
