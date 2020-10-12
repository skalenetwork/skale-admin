import mock
from time import sleep

from core.schains.checks import SChainChecks
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER

from tests.utils import get_schain_contracts_data, run_simple_schain_container


NOT_EXISTS_SCHAIN_NAME = 'qwerty123'
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
TEST_NODE_ID = 0
REMOVING_CONTAINER_WAITING_INTERVAL = 2


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
    assert not checks['needs_repair']


def test_needs_repair_check(skale, dutils):
    test_schain_name = 'needs_repair_test'
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, test_schain_name)
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "exit 200"'
    )
    sleep(10)
    checks = SChainChecks(test_schain_name, TEST_NODE_ID, log=True).get_all()
    assert checks['needs_repair']
