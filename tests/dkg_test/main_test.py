"""
Test for dkg procedure using SGX keys

Usage:
SCHAIN_TYPE=test2/test4/tiny SGX_CERTIFICATES_FOLDER=./tests/dkg_test/ SGX_SERVER_URL=[SGX_SERVER_URL] ENDPOINT=[ENDPOINT] RUNNING_ON_HOST=True SKALE_DIR_HOST=~/.skale python tests/dkg_test/main_test.py  # noqa
"""
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor as Executor

import pytest
import warnings
from skale import Skale
from skale.utils.helper import init_default_logger
from skale.utils.account_tools import send_ether
from skale.wallets import SgxWallet
from skale.utils.contracts_provision.main import cleanup_nodes_schains
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.schains.cleaner import remove_schain_container
from core.schains.config.generator import generate_schain_config_with_skale
from core.schains.dkg import run_dkg
from core.schains.config.dir import init_schain_dir
from tests.conftest import skale as skale_fixture
from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import (generate_random_node_data,
                         generate_random_schain_data, init_web3_skale)
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from core.schains.dkg.utils import init_dkg_client, generate_bls_keys
from core.schains.dkg.client import generate_bls_key_name


MAX_WORKERS = 5
TEST_SRW_FUND_VALUE = 3000000000000000000

owner_skale = init_web3_skale()


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


def register_node(skale, wallet):
    skale.wallet = wallet
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
        'wallet': wallet
    }


def register_nodes(skale, wallets):
    base_wallet = skale.wallet
    nodes = [
        register_node(skale, wallet)
        for wallet in wallets
    ]
    skale.wallet = base_wallet
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


def run_dkg_all(skale, schain_name, nodes):
    futures, results = [], []
    nodes.sort(key=lambda x: x['node_id'])
    with Executor(max_workers=MAX_WORKERS) as executor:
        for i, node_data in enumerate(nodes):
            opts = {
                'index': i,
                'skale': skale,
                'schain_name': schain_name,
                'node_id': node_data['node_id'],
                'wallet': node_data['wallet'],
                'results': results
            }
            futures.append(executor.submit(run_node_dkg, opts))
    for future in futures:
        results.append(future.result())

    bls_public_keys = []
    all_public_keys = []
    for node_data, result in zip(nodes, results):
        assert result['node_id'] == node_data['node_id']
        assert result['dkg_results'] is not None
        bls_public_keys.append(result['dkg_results']['public_key'])
        all_public_keys.append(result['dkg_results']['bls_public_keys'])
        check_config(nodes, node_data, result['config'])

    assert len(results) == N_OF_NODES

    gid = skale.schains.name_to_id(schain_name)
    assert skale.dkg.is_last_dkg_successful(gid)
    return bls_public_keys, all_public_keys
    # todo: add some additional checks that dkg is finished successfully


def run_node_dkg(opts):
    timeout = opts['index'] * 5  # diversify start time for all nodes
    logger.info(f'Node {opts["node_id"]} going to sleep {timeout} seconds')
    time.sleep(timeout)
    skale = skale_fixture()
    skale.wallet = opts['wallet']
    sgx_key_name = skale.wallet._key_name
    schain_name = opts['schain_name']
    node_id = opts['node_id']

    init_schain_dir(schain_name)
    dkg_results = run_dkg(skale, schain_name, opts['node_id'], sgx_key_name)
    print(f'=========================\nDKG DONE: node_id: {node_id} {dkg_results}')

    rotation_id = skale.schains.get_last_rotation_id(schain_name)
    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        node_id=node_id,
        rotation_id=rotation_id,
        ecdsa_key_name=sgx_key_name
    )
    return {
        'node_id': node_id,
        'dkg_results': dkg_results,
        'config': schain_config.to_dict()
    }


def check_fetch_broadcasted_data(skale, schain_name, nodes, bls_public_keys, all_public_keys):
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
    try:
        cleanup_contracts_from_dkg_items(schain_name)
    except Exception as err:
        print(f'Cleaning dkg items from contracts failed {err}')
        error = err
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


def test_init_bls(skale, schain_creation_data, cleanup_dkg):
    schain_name, lifetime = schain_creation_data
    cleanup_nodes_schains(skale)
    wallets = generate_sgx_wallets(skale, N_OF_NODES)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    nodes = register_nodes(skale, wallets)
    create_schain(skale, schain_name, lifetime)
    bls_public_keys, all_public_keys = run_dkg_all(skale, schain_name, nodes)
    check_fetch_broadcasted_data(skale, schain_name, nodes, bls_public_keys, all_public_keys)


if __name__ == "__main__":
    init_default_logger()
    skale = skale_fixture()
    test_init_bls(owner_skale)
