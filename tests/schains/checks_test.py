import mock
import pytest
from time import sleep

from core.schains.skaled_exit_codes import SkaledExitCodes

from core.schains.checks import SChainChecks
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER


from tests.utils import get_schain_contracts_data, run_simple_schain_container


NOT_EXISTS_SCHAIN_NAME = 'qwerty123'
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
TEST_NODE_ID = 0
REMOVING_CONTAINER_WAITING_INTERVAL = 2

CONTAINER_INFO_OK = {'status': 'running'}
CONTAINER_INFO_ERROR = {'status': 'exited'}


@pytest.fixture
def sample_checks(schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    return SChainChecks(schain_name, node_id)


@pytest.fixture
def sample_false_checks():
    return SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID)


def test_data_dir_check(sample_checks, sample_false_checks):
    assert sample_checks.data_dir
    assert not sample_false_checks.data_dir


def test_dkg_check(sample_checks, sample_false_checks):
    assert sample_checks.dkg
    assert not sample_false_checks.dkg


def test_config_check(sample_checks, sample_false_checks):
    assert sample_checks.config
    assert not sample_false_checks.config


def test_volume_check(sample_checks, sample_false_checks):
    with mock.patch('docker.api.client.APIClient.inspect_volume',
                    new=mock.Mock(return_value=True)):
        assert sample_checks.volume
    assert not sample_false_checks.volume


def test_firewall_rules_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.apsent_iptables_rules', return_value=[]):
        assert sample_checks.firewall_rules
    with mock.patch('core.schains.checks.apsent_iptables_rules', return_value=[('1.1.1.1', 1000)]):
        assert not sample_false_checks.firewall_rules


def test_container_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert sample_checks.container
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_ERROR):
        assert not sample_false_checks.container


def test_exit_code_ok_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code', return_value=0):
        assert sample_checks.exit_code_ok
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code',
                    return_value=SkaledExitCodes.EC_STATE_ROOT_MISMATCH):
        assert not sample_false_checks.exit_code_ok


def check_firewall_rules_mock(self):
    self._firewall_rules = True


def check_container_mock(self):
    self._container = True


def test_init_checks(skale):
    schain_name = 'name'
    with mock.patch('core.schains.checks.SChainChecks.check_firewall_rules',
                    new=check_firewall_rules_mock):
        checks = SChainChecks(schain_name, TEST_NODE_ID)
    assert checks.name == schain_name
    assert checks.node_id == TEST_NODE_ID


def test_get_all_checks(skale, schain_config, dutils, cleanup_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    schain_data = get_schain_contracts_data(schain_name)
    run_simple_schain_container(schain_data, dutils)

    with mock.patch('core.schains.checks.SChainChecks.check_firewall_rules',
                    new=check_firewall_rules_mock):
        # skaled is restarting because of bad config permissions
        # TODO: Check permissions and remove mock
        with mock.patch('core.schains.checks.SChainChecks.check_container',
                        new=check_container_mock):
            checks = SChainChecks(schain_name, node_id, log=True).get_all()

    assert checks['data_dir']
    assert checks['dkg']
    assert checks['config']
    assert checks['container']
    # assert not checks['ima_container']
    assert checks['firewall_rules']
    assert not checks['rpc']


def test_get_all_false_checks(skale):
    checks = SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID, log=True).get_all()
    assert not checks['data_dir']
    assert not checks['dkg']
    assert not checks['config']
    assert not checks['container']
    # assert not checks['ima_container']
    assert not checks['firewall_rules']
    assert not checks['rpc']
    assert checks['exit_code_ok']


def _test_exit_code_ok_check(skale, dutils):
    test_schain_name = 'exit_code_ok_test'
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, test_schain_name)
    dutils.safe_rm(container_name)
    try:
        dutils.run_container(
            image_name=image_name,
            name=container_name,
            entrypoint='bash -c "exit 200"'
        )
        sleep(10)
        checks = SChainChecks(test_schain_name, TEST_NODE_ID, log=True).get_all()
        assert not checks['exit_code_ok']
    except Exception as e:
        dutils.safe_rm(container_name)
        raise e
    dutils.safe_rm(container_name)
