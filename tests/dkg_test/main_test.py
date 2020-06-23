"""
Test for dkg procedure using SGX keys

Usage:
SCHAIN_TYPE=test2/test4/tiny SGX_CERTIFICATES_FOLDER=./tests/dkg_test/ SGX_SERVER_URL=[SGX_SERVER_URL] ENDPOINT=[ENDPOINT] RUNNING_ON_HOST=True SKALE_DIR_HOST=~/.skale python tests/dkg_test/main_test.py  # noqa
"""
import logging
from time import sleep

from skale.wallets import SgxWallet
from skale.utils.helper import init_default_logger
from skale.utils.account_tools import send_ether

from core.schains.dkg import init_bls
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.custom_thread import CustomThread

from tests.conftest import skale as skale_fixture
from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import generate_random_node_data, generate_random_schain_data
from tests.prepare_data import cleanup_contracts


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
    logger.info(f'Linking addresses to validator')
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


def run_dkg_all(skale, schain_name, nodes):
    results = []
    dkg_threads = []
    for i, node_data in enumerate(nodes):
        opts = {
            'index': i,
            'skale': skale,
            'schain_name': schain_name,
            'node_id': node_data['node_id'],
            'wallet': node_data['wallet'],
            'results': results
        }
        dkg_thread = CustomThread(
            f'DKG for {node_data["wallet"].address}', run_dkg, opts=opts, once=True)
        dkg_thread.start()
        dkg_threads.append(dkg_thread)
    for dkg_thread in dkg_threads:
        dkg_thread.join()

    assert len(results) == N_OF_NODES
    # todo: add some additional checks that dkg is finished successfully


def run_dkg(opts):
    timeout = opts['index'] * 5  # diversify start time for all nodes
    logger.info(f'Node {opts["node_id"]} going to sleep {timeout} seconds')
    sleep(timeout)
    skale = skale_fixture()
    skale.wallet = opts['wallet']
    sgx_key_name = skale.wallet._key_name
    dkg_results = init_bls(skale, opts['schain_name'], opts['node_id'], sgx_key_name)
    opts['results'].append({
        'node_id': opts["node_id"],
        'dkg_results': dkg_results
    })
    print(f'=========================\nDKG DONE: node_id: {opts["node_id"]} {dkg_results}')


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
