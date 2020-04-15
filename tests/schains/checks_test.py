from time import sleep

from core.schains.checks import SChainChecks
from tools.docker_utils import DockerUtils

from tests.docker_utils_test import run_test_schain_container


SCHAIN_NAME = 'test'
NOT_EXISTS_SCHAIN_NAME = 'qwerty123'
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
TEST_NODE_ID = 0
SKALED_INIT_TIMEOUT = 20


def test_init_checks():
    checks = SChainChecks(SCHAIN_NAME, TEST_NODE_ID)
    assert checks.name == SCHAIN_NAME
    assert checks.node_id == TEST_NODE_ID


def test_get_all_checks():
    dutils = DockerUtils(volume_driver='local')
    dutils.safe_rm('skale_schain_test', force=True)
    dutils.rm_vol(SCHAIN_NAME)

    run_test_schain_container(dutils)
    sleep(SKALED_INIT_TIMEOUT)
    checks = SChainChecks(SCHAIN_NAME, TEST_NODE_ID, log=True).get_all()

    assert checks['data_dir']
    assert checks['dkg']
    assert checks['config']
    assert checks['container']
    assert not checks['ima_container']
    assert not checks['firewall_rules']
    assert checks['rpc']


def test_get_all_false_checks():
    checks = SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID, log=True).get_all()
    assert not checks['data_dir']
    assert not checks['dkg']
    assert not checks['config']
    assert not checks['container']
    assert not checks['ima_container']
    assert not checks['firewall_rules']
    assert not checks['rpc']
