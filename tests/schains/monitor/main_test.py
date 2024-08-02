import functools
import logging
import time
from multiprocessing import Process

import pytest

from core.schains.firewall.types import IpRange
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.monitor.main import Pipeline, run_pipelines

from tools.helper import is_node_part_of_chain


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


def test_run_pipelines():
    def simple_pipeline(index: int):
        logging.info('Running simple pipeline %d', index)
        time.sleep(1)
        logging.info('Finishing simple pipeline %d', index)

    def stuck_pipeline(index: int):
        logging.info('Running stuck pipeline %d', index)
        while True:
            logging.info('Stuck pipeline %d beat', index)
            time.sleep(2)

    target = functools.partial(run_pipelines, pipelines=[
        Pipeline(name='healthy0', job=functools.partial(simple_pipeline, index=0)),
        Pipeline(name='healthy1', job=functools.partial(simple_pipeline, index=1)),
    ], once=True, stuck_timeout=5, shutdown_interval=10)
    monitor_process = Process(target=target)
    monitor_process.start()
    monitor_process.join()

    run_pipelines([
        Pipeline(name='healthy', job=functools.partial(simple_pipeline, index=0)),
        Pipeline(name='stuck', job=functools.partial(stuck_pipeline, index=1))
    ], stuck_timeout=5, shutdown_interval=10)

    monitor_process = Process(target=target)
    monitor_process.start()
    monitor_process.join(timeout=50)
