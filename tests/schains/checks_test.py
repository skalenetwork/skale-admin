import mock
from time import sleep

from core.schains.checks import SChainChecks
from tools.docker_utils import DockerUtils

from tests.docker_utils_test import run_simple_schain_container


SCHAIN_NAME = 'test'
NOT_EXISTS_SCHAIN_NAME = 'qwerty123'
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
TEST_NODE_ID = 0
SKALED_INIT_TIMEOUT = 30


def check_firewall_rules_mock(self):
    self._firewall_rules = True


def cleanup_schain(dutils):
    dutils.safe_rm('skale_schain_test', force=True)
    if dutils.data_volume_exists(SCHAIN_NAME):
        dutils.rm_vol(SCHAIN_NAME)


def test_init_checks(skale):
    with mock.patch('core.schains.checks.SChainChecks.check_firewall_rules',
                    new=check_firewall_rules_mock):
        checks = SChainChecks(SCHAIN_NAME, TEST_NODE_ID)
    assert checks.name == SCHAIN_NAME
    assert checks.node_id == TEST_NODE_ID


def test_get_all_checks(skale):
    dutils = DockerUtils(volume_driver='local')
    cleanup_schain(dutils)
    run_simple_schain_container(dutils)
    sleep(SKALED_INIT_TIMEOUT)

    with mock.patch('core.schains.checks.SChainChecks.check_firewall_rules',
                    new=check_firewall_rules_mock):
        checks = SChainChecks(SCHAIN_NAME, TEST_NODE_ID, log=True).get_all()

    assert checks['data_dir']
    assert checks['dkg']
    assert checks['config']
    assert checks['container']
    # assert not checks['ima_container']
    assert checks['firewall_rules']
    assert not checks['rpc']
    cleanup_schain(dutils)


def test_get_all_false_checks(skale):
    checks = SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID, log=True).get_all()
    assert not checks['data_dir']
    assert not checks['dkg']
    assert not checks['config']
    assert not checks['container']
    # assert not checks['ima_container']
    assert not checks['firewall_rules']
    assert not checks['rpc']
