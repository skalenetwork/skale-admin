import mock
import pytest

from core.schains.monitor import BaseMonitor
from core.schains.ima import ImaData
from core.schains.checks import SChainChecks
from core.schains.cleaner import remove_ima_container
from core.schains.config.generator import save_schain_config
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER

from web.models.schain import SChainRecord

from tests.dkg_utils import safe_run_dkg_mock


class BaseTestMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        return 1234

    def _run_all_checks(self):
        pass


class CrashingTestMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        raise Exception('Something went wrong')

    def _run_all_checks(self):
        pass


def init_schain_config_mock(
    skale,
    node_id,
    schain_name,
    ecdsa_sgx_key_name,
    rotation_id,
    schain_record
):
    save_schain_config({}, schain_name)


def monitor_schain_container_mock(
    schain,
    schain_record,
    public_key=None,
    start_ts=None,
    volume_required=True,
    dutils=None
):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


def run_ima_container_mock(schain: dict, mainnet_chain_id: int, dutils=None):
    image_name, container_name, _, _ = get_container_info(
        IMA_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


@pytest.fixture
def test_monitor(schain_db, node_config, skale, ima_data, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    schain_checks = SChainChecks(
        schain_db,
        node_config.id,
        schain_record=schain_record,
        dutils=dutils
    )
    return BaseTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain={'name': schain_db, 'partOfNode': 0},
        node_config=node_config,
        rotation_data={'rotation_id': 0, 'finish_ts': 0},
        checks=schain_checks,
        dutils=dutils
    )


def test_crashing_monitor(schain_db, skale, node_config, schain_checks, ima_data, schain_struct):
    test_monitor = CrashingTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain_struct,
        node_config=node_config,
        rotation_data={'rotation_id': 1},
        checks=schain_checks
    )
    with pytest.raises(Exception):
        test_monitor.run()


def test_base_monitor(test_monitor):
    assert test_monitor.run() == 1234


def test_base_monitor_config_dir(test_monitor):
    assert not test_monitor.config_dir()
    assert test_monitor.config_dir()


def test_base_monitor_dkg(test_monitor):
    test_monitor.config_dir()
    with mock.patch('core.schains.monitor.base_monitor.safe_run_dkg', safe_run_dkg_mock):
        assert not test_monitor.dkg()
        assert test_monitor.dkg()


def test_base_monitor_config(test_monitor):
    test_monitor.config_dir()
    with mock.patch(
            'core.schains.monitor.base_monitor.init_schain_config', init_schain_config_mock):
        assert not test_monitor.config()
        assert test_monitor.config()


def test_base_monitor_volume(test_monitor):
    test_monitor.config_dir()
    assert not test_monitor.volume()
    assert test_monitor.volume()
    test_monitor.cleanup_schain_docker_entity()


def test_base_monitor_skaled_container(test_monitor):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        monitor_schain_container_mock
    ):
        assert not test_monitor.skaled_container()
        assert test_monitor.skaled_container()
    test_monitor.cleanup_schain_docker_entity()


def test_base_monitor_skaled_container_sync(test_monitor):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        new=mock.Mock()
    ) as monitor_schain_mock:
        test_monitor.skaled_container(sync=True)

    monitor_schain_mock.assert_called_with(
        test_monitor.schain,
        schain_record=test_monitor.schain_record,
        public_key='0:0:1:0',
        start_ts=0,
        dutils=test_monitor.dutils
    )
    assert monitor_schain_mock.call_count == 1


def test_base_monitor_ima_container(test_monitor):
    test_monitor.config_dir()
    with mock.patch(
        'core.schains.monitor.base_monitor.run_ima_container',
        run_ima_container_mock
    ):
        assert not test_monitor.ima_container()
        assert test_monitor.ima_container()
    remove_ima_container(test_monitor.name, dutils=test_monitor.dutils)


def test_base_monitor_ima_container_not_linked(schain_db, node_config, skale, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    schain_checks = SChainChecks(
        schain_db,
        node_config.id,
        schain_record=schain_record,
        dutils=dutils
    )
    ima_data = ImaData(False, '0x1')
    test_monitor = BaseTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain={'name': schain_db, 'partOfNode': 0},
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks,
        dutils=dutils
    )

    test_monitor.config_dir()
    assert not test_monitor.ima_container()
    assert not test_monitor.ima_container()
    remove_ima_container(test_monitor.name, dutils=test_monitor.dutils)


def test_base_monitor_cleanup(test_monitor):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        monitor_schain_container_mock
    ):
        test_monitor.skaled_container()

    assert test_monitor.checks.volume.status
    assert test_monitor.checks.skaled_container.status
    test_monitor.cleanup_schain_docker_entity()
    assert not test_monitor.checks.volume.status
    assert not test_monitor.checks.skaled_container.status