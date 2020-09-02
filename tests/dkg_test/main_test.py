"""
Test for dkg procedure using SGX keys

Usage:
SCHAIN_TYPE=test2/test4/tiny SGX_CERTIFICATES_FOLDER=./tests/dkg_test/ SGX_SERVER_URL=[SGX_SERVER_URL] ENDPOINT=[ENDPOINT] RUNNING_ON_HOST=True SKALE_DIR_HOST=~/.skale python tests/dkg_test/main_test.py  # noqa
"""
import logging
from time import sleep
from concurrent.futures import ThreadPoolExecutor as Executor

from skale.wallets import SgxWallet
from skale.utils.helper import init_default_logger
from skale.utils.account_tools import send_ether

from core.schains.config.generator import generate_schain_config_with_skale
from core.schains.dkg import run_dkg
from core.schains.helper import init_schain_dir
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER

from tests.conftest import skale as skale_fixture
from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import generate_random_node_data, generate_random_schain_data
from tests.prepare_data import cleanup_contracts


MAX_WORKERS = 5

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
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)
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
            'imaMainNet', 'imaMessageProxySChain', 'imaMessageProxyMainNet',
            'rotateAfterBlock', 'ecdsaKeyName', 'wallets', 'minCacheSize',
            'maxCacheSize', 'collectionQueueSize', 'collectionDuration',
            'transactionQueueSize', 'maxOpenLeveldbFiles']
    check_keys(info, keys)
    assert info['nodeID'] == node_data['node_id']
    check_node_ports(info)
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
        ['schainID', 'schainName', 'schainOwner', 'storageLimit',
         'snapshotIntervalMs', 'emptyBlockIntervalMs',
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

    for node_data, result in zip(nodes, results):
        assert result['node_id'] == node_data['node_id']
        assert result['dkg_results'] is None
        check_config(nodes, node_data, result['config'])

    assert len(results) == N_OF_NODES
    # todo: add some additional checks that dkg is finished successfully


def run_node_dkg(opts):
    timeout = opts['index'] * 5  # diversify start time for all nodes
    logger.info(f'Node {opts["node_id"]} going to sleep {timeout} seconds')
    sleep(timeout)
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


def create_schain(skale):
    _, lifetime_seconds, name = generate_random_schain_data()
    price_in_wei = skale.schains.get_schain_price(TYPE_OF_NODES, lifetime_seconds)
    skale.manager.create_schain(
        lifetime_seconds,
        TYPE_OF_NODES,
        price_in_wei,
        name,
        wait_for=True
    )
    return name


def test_init_bls(skale):
    cleanup_contracts(skale)
    wallets = generate_sgx_wallets(skale, N_OF_NODES)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    nodes = register_nodes(skale, wallets)
    schain_name = create_schain(skale)
    run_dkg_all(skale, schain_name, nodes)


if __name__ == "__main__":
    init_default_logger()
    skale = skale_fixture()
    test_init_bls(skale)
