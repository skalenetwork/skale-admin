import mock
import pytest

from core.schains.checks import SChainChecks
from core.schains.cleaner import remove_ima_container
from core.schains.config.main import save_schain_config
from core.schains.ima import ImaData
from core.schains.monitor import BaseMonitor
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from web.models.schain import SChainRecord

from tests.dkg_utils import safe_run_dkg_mock
from tests.utils import get_test_rule_controller


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
    generation,
    ecdsa_sgx_key_name,
    rotation_data,
    schain_record
):
    save_schain_config({}, schain_name)


def monitor_schain_container_mock(
    schain,
    schain_record,
    skaled_status,
    public_key=None,
    start_ts=None,
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
def test_monitor(
    schain_db,
    _schain_name,
    node_config,
    uninited_rule_controller,
    skale,
    ima_data,
    dutils
):
    schain_record = SChainRecord.get_by_name(_schain_name)
    schain_checks = SChainChecks(
        _schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=uninited_rule_controller,
        dutils=dutils
    )
    return BaseTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain={'name': schain_db, 'partOfNode': 0, 'generation': 0},
        node_config=node_config,
        rotation_data={'rotation_id': 0, 'finish_ts': 0, 'leaving_node': 1},
        checks=schain_checks,
        rule_controller=uninited_rule_controller,
        dutils=dutils
    )


def test_crashing_monitor(
    schain_db,
    _schain_name,
    skale,
    node_config,
    rule_controller,
    ima_data,
    schain_struct,
    dutils
):
    schain_record = SChainRecord.get_by_name(_schain_name)
    schain_checks = SChainChecks(
        _schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )
    test_monitor = CrashingTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain_struct,
        node_config=node_config,
        rotation_data={'rotation_id': 1, 'leaving_node': 1},
        checks=schain_checks,
        rule_controller=rule_controller
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
        test_monitor.skaled_container(download_snapshot=True)

    monitor_schain_mock.assert_called_with(
        test_monitor.schain,
        schain_record=test_monitor.schain_record,
        skaled_status=test_monitor.skaled_status,
        public_key='0:0:1:0',
        start_ts=None,
        dutils=test_monitor.dutils
    )
    assert monitor_schain_mock.call_count == 1


def test_base_monitor_skaled_container_sync_delay_start(test_monitor):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        new=mock.Mock()
    ) as monitor_schain_mock:
        test_monitor.finish_ts = 1245
        test_monitor.skaled_container(download_snapshot=True, delay_start=True)

    monitor_schain_mock.assert_called_with(
        test_monitor.schain,
        schain_record=test_monitor.schain_record,
        skaled_status=test_monitor.skaled_status,
        public_key='0:0:1:0',
        start_ts=1245,
        dutils=test_monitor.dutils
    )
    assert monitor_schain_mock.call_count == 1


def test_base_monitor_restart_skaled_container(test_monitor):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        monitor_schain_container_mock
    ):
        assert not test_monitor.restart_skaled_container()
        assert test_monitor.restart_skaled_container()
    test_monitor.cleanup_schain_docker_entity()


def test_base_monitor_ima_container(test_monitor, schain_config):
    test_monitor.config_dir()
    test_monitor.ima_data.linked = True
    with mock.patch(
        'core.schains.monitor.containers.run_ima_container',
        run_ima_container_mock
    ):
        assert not test_monitor.ima_container()
        assert test_monitor.ima_container()
    remove_ima_container(test_monitor.name, dutils=test_monitor.dutils)


def test_base_monitor_ima_container_not_linked(
    schain_db,
    _schain_name,
    node_config,
    skale,
    dutils
):
    schain_record = SChainRecord.get_by_name(_schain_name)
    schain_checks = SChainChecks(
        _schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=get_test_rule_controller(_schain_name),
        dutils=dutils
    )
    ima_data = ImaData(False, '0x1')
    test_monitor = BaseTestMonitor(
        skale=skale,
        ima_data=ima_data,
        schain={'name': schain_db, 'partOfNode': 0, 'generation': 0},
        node_config=node_config,
        rotation_data={'rotation_id': 0, 'leaving_node': 1},
        checks=schain_checks,
        rule_controller=get_test_rule_controller(_schain_name),
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


def test_schain_finish_ts(skale, schain_on_contracts):
    name = schain_on_contracts
    max_node_id = skale.nodes.get_nodes_number() - 1
    assert skale.node_rotation.get_schain_finish_ts(max_node_id, name) is None


def test_display_skaled_logs(skale, test_monitor, _schain_name):
    test_monitor.volume()
    with mock.patch(
        'core.schains.monitor.base_monitor.monitor_schain_container',
        monitor_schain_container_mock
    ):
        test_monitor.skaled_container()
    test_monitor.display_skaled_logs()
