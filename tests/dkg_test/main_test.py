"""
Test for dkg procedure using SGX keys
"""
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor as Executor

import mock
import pytest
import warnings
from skale import Skale
from skale.utils.account_tools import send_ether
from skale.wallets import SgxWallet
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.schains.cleaner import remove_schain_container
# from core.schains.config.generator import generate_schain_config_with_skale
from core.schains.dkg import get_dkg_client, is_last_dkg_finished, safe_run_dkg
from core.schains.helper import init_schain_dir
from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import (
    generate_random_node_data,
    generate_random_schain_data,
    init_skale_from_wallet,
    init_web3_skale
)
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.bls.dkg_utils import DKGKeyGenerationError, generate_bls_keys
from tools.bls.dkg_client import DkgError
# from tools.logger import init_logger, Formatter

warnings.filterwarnings("ignore")

MAX_WORKERS = 5
TEST_SRW_FUND_VALUE = 3000000000000000000

log_format = '[%(asctime)s][%(levelname)s] - %(threadName)s - %(name)s:%(lineno)d - %(message)s'  # noqa

# init_logger(Formatter, log_format)

logger = logging.getLogger(__name__)


class DkgTestError(Exception):
    pass


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
    logger.info(
        f'Transfering {TEST_ETH_AMOUNT} ETH to {len(wallets)} test wallets'
    )
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


def register_nodes(skale_instances):
    nodes = [
        register_node(sk)
        for sk in skale_instances
    ]
    return nodes


def run_dkg_all(skale, skale_sgx_instances, schain_name, nodes):
    futures = []
    nodes.sort(key=lambda x: x['node_id'])
    with Executor(max_workers=MAX_WORKERS) as executor:
        for i, (node_skale, node_data) in \
                enumerate(zip(skale_sgx_instances, nodes)):
            futures.append(executor.submit(
                run_node_dkg,
                node_skale, schain_name, i, node_data['node_id']
            ))

    return [f.result() for f in futures]


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


def cleanup_contracts_from_dkg_items(skale: Skale, schain_name: str) -> None:
    node_ids = skale.schains_internal.get_node_ids_for_schain(schain_name)
    skale.manager.delete_schain(schain_name)
    for node_id in node_ids:
        skale.manager.node_exit(node_id)


def cleanup_docker_items(schain_name: str) -> None:
    remove_schain_container(schain_name)
    # remove_schain_volume(schain_name)


def cleanup_schain_configs(schain_name: str) -> None:
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    subprocess.run(['rm', '-rf', schain_dir_path])


@pytest.fixture
def cleanup_dkg(skale, schain_creation_data):
    yield
    error = None
    schain_name, _ = schain_creation_data
    # try:
    #     cleanup_contracts_from_dkg_items(skale, schain_name)
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


def remove_schain(skale, schain_name):
    print('Cleanup nodes and schains')
    if schain_name is not None:
        skale.manager.delete_schain(schain_name, wait_for=True)


def remove_nodes(skale, nodes):
    for node_id in nodes:
        skale.manager.node_exit(node_id, wait_for=True)


@pytest.mark.skip
def test_failed_get_dkg_client(skale):
    skale.schains_internal.get_node_ids_for_schain = mock.Mock(return_value=[])
    with pytest.raises(DkgError):
        get_dkg_client(
            node_id=0,
            schain_name='fake-schain',
            skale=skale,
            sgx_key_name='fake-sgx-keyname',
            rotation_id=0
        )


@pytest.mark.skip
def test_failed_generate_bls_keys(skale):
    skale.schains_internal.get_node_ids_for_schain = mock.Mock(return_value=[])
    skale.key_storage.get_common_public_key = mock.Mock(
        side_effect=DkgTestError('Key storage operation failed')
    )
    dkg_client = get_dkg_client(
        node_id=0,
        schain_name='fake-schain',
        skale=skale,
        sgx_key_name='faike-sgx-keyname',
        rotation_id=0
    )
    with pytest.raises(DKGKeyGenerationError):
        generate_bls_keys(dkg_client)


class TestDKG:
    @pytest.fixture(scope='class')
    def skale(self):
        return init_web3_skale()

    @pytest.fixture(scope='class')
    def schain_creation_data(self):
        _, lifetime_seconds, name = generate_random_schain_data()
        return name, lifetime_seconds

    @pytest.fixture(scope='class')
    def sgx_wallets(self, skale):
        wallets = generate_sgx_wallets(skale, N_OF_NODES)
        transfer_eth_to_wallets(skale, wallets)
        link_addresses_to_validator(skale, wallets)
        return wallets

    @pytest.fixture(scope='class')
    def skale_sgx_instances(self, skale, sgx_wallets):
        return [
            init_skale_from_wallet(w)
            for w in sgx_wallets
        ]

    @pytest.fixture(scope='class')
    def other_maintenance(self, skale):
        nodes = skale.nodes.get_active_node_ids()
        for nid in nodes:
            skale.nodes.set_node_in_maintenance(nid)
        yield
        for nid in nodes:
            skale.nodes.remove_node_from_in_maintenance(nid)

    @pytest.fixture(scope='class')
    def nodes(self, skale, skale_sgx_instances, other_maintenance):
        nodes = register_nodes(skale_sgx_instances)
        try:
            yield nodes
        finally:
            return
            nids = [node['node_id'] for node in nodes]
            remove_nodes(skale, nids)

    @pytest.fixture(scope='class')
    def schain(self, schain_creation_data, skale, nodes):
        schain_name, lifetime = schain_creation_data
        create_schain(skale, schain_name, lifetime)
        try:
            yield schain_name
        finally:
            remove_schain(skale, schain_name)

    def test_regular_dkg(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        results = run_dkg_all(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )
        assert len(results) == N_OF_NODES
        assert is_last_dkg_finished(skale, schain_name)

        bls_public_keys, all_public_keys = [], []
        for node_data, result in zip(nodes, results):
            assert result.status.is_done()
            keys_data = result.keys_data
            assert keys_data is not None
            bls_public_keys.append(keys_data['public_key'])
            all_public_keys.append(keys_data['bls_public_keys'])
            # check_config(nodes, node_data, result['config'])

        gid = skale.schains.name_to_id(schain_name)
        assert skale.dkg.is_last_dkg_successful(gid)

    def test_dkg_restore_keys(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        schain
    ):
        # Rerun dkg to regenerate keys
        schain_name, _ = schain_creation_data
        results = run_dkg_all(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )
        assert all([r.status.is_done() for r in results])
        assert is_last_dkg_finished(skale, schain_name)
