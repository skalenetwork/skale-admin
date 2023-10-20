import mock
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.schains.firewall.types import IpRange
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.monitor.main import run_monitor_for_schain
from core.schains.task import Task

from tools.helper import is_node_part_of_chain
from web.models.schain import upsert_schain_record


@pytest.fixture
def sync_ranges(skale):
    skale.sync_manager.grant_sync_manager_role(skale.wallet.address)
    skale.sync_manager.add_ip_range('test1', '127.0.0.1', '127.0.0.2')
    skale.sync_manager.add_ip_range('test2', '127.0.0.5', '127.0.0.7')
    try:
        yield
    finally:
        skale.sync_manager.remove_ip_range('test1')
        skale.sync_manager.remove_ip_range('test2')


def test_get_sync_agent_ranges(skale, sync_ranges):
    ranges = get_sync_agent_ranges(skale)
    assert ranges == [
        IpRange(start_ip='127.0.0.1', end_ip='127.0.0.2'),
        IpRange(start_ip='127.0.0.5', end_ip='127.0.0.7')
    ]


def test_get_sync_agent_ranges_empty(skale):
    ranges = get_sync_agent_ranges(skale)
    assert ranges == []


def test_is_node_part_of_chain(skale, schain_on_contracts, node_config):
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, node_config.id)
    assert chain_on_node

    chain_on_node = is_node_part_of_chain(skale, 'a', node_config.id)
    assert not chain_on_node

    node_exist_node = 10000
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, node_exist_node)
    assert not chain_on_node


def test_run_monitor_for_schain(
    skale,
    skale_ima,
    schain_on_contracts,
    node_config,
    schain_db,
    dutils
):
    with mock.patch('core.schains.monitor.main.keep_tasks_running') as keep_tasks_running_mock:
        run_monitor_for_schain(
            skale,
            skale_ima,
            node_config,
            schain={'name': schain_db, 'partOfNode': 0, 'generation': 0},
            dutils=dutils,
            once=True
        )
        assert isinstance(keep_tasks_running_mock.call_args[0][0], ThreadPoolExecutor)
        assert isinstance(keep_tasks_running_mock.call_args[0][1][0], Task)
        assert isinstance(keep_tasks_running_mock.call_args[0][1][1], Task)
        assert keep_tasks_running_mock.call_args[0][2] == [None, None]


def test_run_monitor_for_schain_left(
    skale,
    skale_ima,
    node_config,
    schain_db,
    dutils
):
    schain_not_exists = 'not-on-node'
    upsert_schain_record(schain_not_exists)
    with mock.patch('core.schains.monitor.main.keep_tasks_running') as keep_tasks_running_mock:
        run_monitor_for_schain(
            skale,
            skale_ima,
            node_config,
            schain={'name': schain_not_exists, 'partOfNode': 0, 'generation': 0},
            dutils=dutils,
            once=True
        )
        keep_tasks_running_mock.assert_not_called()
