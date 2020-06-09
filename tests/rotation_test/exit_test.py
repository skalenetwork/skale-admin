from unittest import mock

import pytest

from core.node import Node
from core.node_config import NodeConfig
from core.schains.creator import monitor
from tests.dkg_test.main_test import run_dkg
from tests.utils import generate_random_node_data
from tools.custom_thread import CustomThread
from web.models.schain import SChainRecord


def run_dkg_all(skale, schain_name, node_ids):
    results = []
    dkg_threads = []
    for i, node_id in enumerate(node_ids):
        opts = {
            'index': i,
            'skale': skale,
            'schain_name': schain_name,
            'node_id': node_id,
            'wallet': skale.wallet,
            'results': results
        }
        dkg_thread = CustomThread(
            f'DKG for {skale.address}', run_dkg, opts=opts, once=True)
        dkg_thread.start()
        dkg_threads.append(dkg_thread)
    for dkg_thread in dkg_threads:
        dkg_thread.join()


@pytest.fixture
def exiting_node(skale):
    name = 'exit_test'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)
    config = NodeConfig()
    config.id = skale.nodes_data.node_name_to_index(name)

    name = f'rotation_test_0'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)

    schain_name = 'exit_schain'
    skale.manager.create_default_schain(schain_name)

    run_dkg_all(skale, schain_name, [skale.nodes_data.node_name_to_index(name)])

    name = f'rotation_test_1'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)

    yield Node(skale, config)
    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(2):
        name = f'rotation_test_{i}'
        id = skale.nodes_data.node_name_to_index(name)
        skale.manager.delete_node_by_root(id, wait_for=True)


def test_node_exit(skale, exiting_node):
    SChainRecord.create_table()
    # with mock.patch('core.schains.creator.run_dkg'):
    monitor(skale, exiting_node.config)
    assert False