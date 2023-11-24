"""
Test for dkg procedure using SGX keys
"""
import functools
import logging
import os
import subprocess
import time
from concurrent.futures import Future, ThreadPoolExecutor as Executor
from contextlib import contextmanager
from enum import Enum

import mock
import pytest
import warnings
from skale import Skale
from skale.utils.account_tools import send_eth
from skale.wallets import SgxWallet
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.schains.dkg.main import get_dkg_client, is_last_dkg_finished, safe_run_dkg
from core.schains.dkg.status import DKGStatus, DKGStep
from core.schains.config import init_schain_config_dir

from tests.dkg_test import N_OF_NODES, TEST_ETH_AMOUNT, TYPE_OF_NODES
from tests.utils import (
    generate_random_node_data,
    generate_random_schain_data,
    init_skale_from_wallet
)
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from core.schains.dkg.utils import DKGKeyGenerationError, generate_bls_keys
from core.schains.dkg.client import DkgError

warnings.filterwarnings("ignore")

MAX_WORKERS = 5
TEST_SRW_FUND_VALUE = 3000000000000000000
DKG_TIMEOUT = 200000  # mainnet test client may have current time in the future
DKG_TIMEOUT_FOR_FAILURE = 100000  # to speed up failed broadcast/alright test

log_format = '[%(asctime)s][%(levelname)s] - %(threadName)s - %(name)s:%(lineno)d - %(message)s'  # noqa

logger = logging.getLogger(__name__)


class DkgTestError(Exception):
    pass


class DKGRunType(int, Enum):
    NORMAL = 0
    BROADCAST_FAILED = 1
    ALRIGHT_FAILED = 2
    COMPLAINT_FAILED = 3


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
        signature=signature
    )


def transfer_eth_to_wallets(skale, wallets):
    logger.info(
        f'Transfering {TEST_ETH_AMOUNT} ETH to {len(wallets)} test wallets'
    )
    for wallet in wallets:
        send_eth(skale.web3, skale.wallet, wallet.address, TEST_ETH_AMOUNT)


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
        domain_name=DEFAULT_DOMAIN_NAME
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


def exec_dkg_runners(runners: list[Future]):
    with Executor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(runner)
            for runner in runners
        ]
        return [f.result() for f in futures]


def get_dkg_runners(skale, skale_sgx_instances, schain_name, nodes):
    runners = []
    for i, (node_skale, node_data) in \
            enumerate(zip(skale_sgx_instances, nodes)):
        runners.append(functools.partial(
            run_node_dkg,
            node_skale,
            schain_name,
            i,
            node_data['node_id']
        ))

    return runners


@contextmanager
def dkg_test_client(
    skale: Skale,
    node_id: int,
    schain_name: str,
    sgx_key_name: str,
    rotation_id: int,
    run_type: DKGRunType = DKGRunType.NORMAL
):
    dkg_client = get_dkg_client(node_id, schain_name, skale, sgx_key_name, rotation_id)
    method, original = None, None
    if run_type == DKGRunType.BROADCAST_FAILED:
        effect = DkgError('Broadcast failed on purpose')
        method, original = 'broadcast', dkg_client.skale.dkg.broadcast
        dkg_client.skale.dkg.broadcast = mock.Mock(side_effect=effect)
    elif run_type == DKGRunType.ALRIGHT_FAILED:
        effect = DkgError('Alright failed on purpose')
        method, original = 'alright', dkg_client.skale.dkg.alright
        dkg_client.skale.dkg.alright = mock.Mock(side_effect=effect)
    elif run_type == DKGRunType.COMPLAINT_FAILED:
        effect = DkgError('Complaint failed on purpose')
        method, original = 'complaint', dkg_client.skale.dkg.complaint
        dkg_client.skale.dkg.complaint = mock.Mock(side_effect=effect)

    try:
        yield dkg_client
    finally:
        if method:
            setattr(dkg_client.skale.dkg, method, original)


def run_node_dkg(
    skale: Skale,
    schain_name: str,
    index: int,
    node_id: int,
    runs: tuple[DKGRunType] = (DKGRunType.NORMAL,)
):
    init_schain_config_dir(schain_name)
    sgx_key_name = skale.wallet._key_name
    rotation_id = skale.schains.get_last_rotation_id(schain_name)

    timeout = index * 5  # diversify start time for all nodes
    logger.info('Node %d going to sleep %d seconds %s', node_id, timeout, type(runs))
    time.sleep(timeout)
    logger.info('Starting runs %s, %d', runs, len(runs))
    dkg_result = None
    for run_type in runs:
        logger.info('Running %s dkg', run_type)
        with dkg_test_client(
            skale,
            node_id,
            schain_name,
            sgx_key_name,
            rotation_id,
            run_type
        ) as dkg_client:
            logger.info('ID skale %d', id(dkg_client.skale))
            try:
                dkg_result = safe_run_dkg(
                    skale,
                    dkg_client,
                    schain_name,
                    node_id,
                    sgx_key_name,
                    rotation_id
                )
            except Exception:
                logger.exception('DKG run failed')
            else:
                if dkg_result.status == DKGStatus.DONE:
                    logger.info('DKG completed')
                    break
        logger.info('Finished run %s', run_type)

    logger.info('Completed runs %s', runs)
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
        value=TEST_SRW_FUND_VALUE
    )


def cleanup_schain_config(schain_name: str) -> None:
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    subprocess.run(['rm', '-rf', schain_dir_path])


def remove_schain(skale, schain_name):
    print('Cleanup nodes and schains')
    if schain_name is not None:
        skale.manager.delete_schain(schain_name)


def remove_nodes(skale, nodes):
    for node_id in nodes:
        skale.nodes.init_exit(node_id)
        skale.manager.node_exit(node_id)


class TestDKG:
    @pytest.fixture
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
    def nodes(self, skale, validator, skale_sgx_instances, other_maintenance):
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
    def dkg_timeout_small(self, skale):
        skale.constants_holder.set_complaint_timelimit(DKG_TIMEOUT_FOR_FAILURE)

    @pytest.fixture
    def schain(self, schain_creation_data, skale, nodes):
        schain_name, lifetime = schain_creation_data
        create_schain(skale, schain_name, lifetime)
        try:
            yield schain_name
        finally:
            remove_schain(skale, schain_name)
            cleanup_schain_config(schain_name)

    def test_dkg_procedure_normal(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        assert is_last_dkg_finished(skale, schain_name)

        for node_data, result in zip(nodes, results):
            assert result.status.is_done()
            assert result.step == DKGStep.KEY_GENERATION
            keys_data = result.keys_data
            assert keys_data is not None
        gid = skale.schains.name_to_id(schain_name)
        assert skale.dkg.is_last_dkg_successful(gid)

        regular_dkg_keys_data = sorted(
            [r.keys_data for r in results], key=lambda d: d['n']
        )
        time.sleep(3)
        # Rerun dkg to emulate restoring keys

        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )
        results = exec_dkg_runners(runners)
        assert all([r.status.is_done() for r in results])
        assert is_last_dkg_finished(skale, schain_name)

        restore_dkg_keys_data = sorted(
            [r.keys_data for r in results], key=lambda d: d['n']
        )
        assert regular_dkg_keys_data == restore_dkg_keys_data

    def test_dkg_procedure_broadcast_failed_completely(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout_small,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )

        runners[0] = functools.partial(
            run_node_dkg,
            skale_sgx_instances[0],
            schain_name,
            0,
            nodes[0]['node_id'],
            runs=(DKGRunType.BROADCAST_FAILED,)
        )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        gid = skale.schains.name_to_id(schain_name)

        for i, (node_data, result) in enumerate(zip(nodes, results)):
            assert result.status == DKGStatus.FAILED
            if i == 0:
                assert result.step == DKGStep.BROADCAST
            else:
                assert result.step == DKGStep.COMPLAINT_NO_BROADCAST
            assert result.keys_data is None
        assert not skale.dkg.is_last_dkg_successful(gid)
        assert not is_last_dkg_finished(skale, schain_name)

    def test_dkg_procedure_broadcast_failed_once(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout_small,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )

        runners[0] = functools.partial(
            run_node_dkg,
            skale_sgx_instances[0],
            schain_name,
            0,
            nodes[0]['node_id'],
            runs=(DKGRunType.BROADCAST_FAILED, DKGRunType.NORMAL)
        )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        gid = skale.schains.name_to_id(schain_name)

        for i, (node_data, result) in enumerate(zip(nodes, results)):
            assert result.status == DKGStatus.DONE
            assert result.step == DKGStep.KEY_GENERATION
            assert result.keys_data is not None
        assert skale.dkg.is_last_dkg_successful(gid)
        assert is_last_dkg_finished(skale, schain_name)

    def test_dkg_procedure_alright_failed_completely(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout_small,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )

        runners[0] = functools.partial(
            run_node_dkg,
            skale_sgx_instances[0],
            schain_name,
            0,
            nodes[0]['node_id'],
            runs=(DKGRunType.ALRIGHT_FAILED,)
        )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        gid = skale.schains.name_to_id(schain_name)

        for i, (node_data, result) in enumerate(zip(nodes, results)):
            assert result.status == DKGStatus.FAILED
            if i == 0:
                assert result.step == DKGStep.BROADCAST_VERIFICATION
            else:
                assert result.step == DKGStep.COMPLAINT_NO_ALRIGHT
            assert result.keys_data is None
        assert not skale.dkg.is_last_dkg_successful(gid)
        assert not is_last_dkg_finished(skale, schain_name)

    def test_dkg_procedure_alright_failed_once(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout_small,
        schain
    ):
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )

        runners[0] = functools.partial(
            run_node_dkg,
            skale_sgx_instances[0],
            schain_name,
            0,
            nodes[0]['node_id'],
            runs=(DKGRunType.ALRIGHT_FAILED, DKGRunType.NORMAL)
        )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        gid = skale.schains.name_to_id(schain_name)

        for i, (node_data, result) in enumerate(zip(nodes, results)):
            assert result.status == DKGStatus.DONE
            assert result.step == DKGStep.KEY_GENERATION
            assert result.keys_data is not None
        assert skale.dkg.is_last_dkg_successful(gid)
        assert is_last_dkg_finished(skale, schain_name)

    def test_dkg_procedure_complaint_failed(
        self,
        skale,
        schain_creation_data,
        skale_sgx_instances,
        nodes,
        dkg_timeout_small,
        schain
    ):
        # TODO: Same as broadcast failed. Fix this test'
        schain_name, _ = schain_creation_data
        assert not is_last_dkg_finished(skale, schain_name)
        nodes.sort(key=lambda x: x['node_id'])
        runners = get_dkg_runners(
            skale,
            skale_sgx_instances,
            schain_name,
            nodes
        )

        runners[0] = functools.partial(
            run_node_dkg,
            skale_sgx_instances[0],
            schain_name,
            0,
            nodes[0]['node_id'],
            runs=(DKGRunType.BROADCAST_FAILED,)
        )
        for i in range(1, N_OF_NODES):
            runners[i] = functools.partial(
                run_node_dkg,
                skale_sgx_instances[i],
                schain_name,
                i,
                nodes[i]['node_id'],
                runs=(DKGRunType.COMPLAINT_FAILED,)
            )
        results = exec_dkg_runners(runners)
        assert len(results) == N_OF_NODES
        gid = skale.schains.name_to_id(schain_name)

        for i, (node_data, result) in enumerate(zip(nodes, results)):
            assert result.status == DKGStatus.FAILED
            if i == 0:
                assert result.step == DKGStep.BROADCAST
            else:
                assert result.step == DKGStep.COMPLAINT_NO_BROADCAST
            assert result.keys_data is None
        assert not skale.dkg.is_last_dkg_successful(gid)
        assert not is_last_dkg_finished(skale, schain_name)

    @pytest.fixture
    def no_ids_for_schain_skale(self, skale):
        get_node_ids_f = skale.schains_internal.get_node_ids_for_schain
        try:
            skale.t
            skale.schains_internal.get_node_ids_for_schain = mock.Mock(
                return_value=[]
            )

            skale.constants_holder.get_dkg_timeout = mock.Mock(return_value=2)
            yield skale
        finally:
            skale.schains_internal.get_node_ids_for_schain = get_node_ids_f

    def test_failed_get_dkg_client(self, no_ids_for_schain_skale, schain):
        skale = no_ids_for_schain_skale
        with pytest.raises(DkgError):
            get_dkg_client(
                node_id=0,
                schain_name='fake-schain',
                skale=skale,
                sgx_key_name='fake-sgx-keyname',
                rotation_id=0
            )

    @pytest.mark.skip
    def test_failed_generate_bls_keys(
        self,
        skale,
        skale_sgx_instances,
        nodes,
        schain
    ):
        skale.key_storage.get_common_public_key = mock.Mock(
            side_effect=DkgTestError('Key storage operation failed')
        )
        dkg_client = get_dkg_client(
            node_id=nodes[0]['node_id'],
            schain_name=schain,
            skale=skale,
            sgx_key_name=skale_sgx_instances[0],
            rotation_id=0
        )
        with pytest.raises(DKGKeyGenerationError):
            generate_bls_keys(dkg_client)
