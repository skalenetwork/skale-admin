import shutil
from time import time
from unittest import mock

import pytest
import os

from tests.rotation_test.utils import (wait_for_contract_exiting, wait_for_schain_alive,
                                       wait_for_schain_exiting, check_schain_alive,
                                       get_spawn_skale_mock, set_up_nodes, run_dkg_mock,
                                       init_data_volume_mock, run_schain_container_mock)
from skale.manager_client import spawn_skale_lib

from core.node import Node, NodeExitStatuses, SchainExitStatuses
from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.cleaner import monitor as cleaner_monitor
from core.schains.creator import monitor
from tests.dkg_test.main_test import run_dkg_all
from tests.prepare_data import cleanup_contracts
from tests.utils import generate_random_name
from tools.configs.schains import SCHAINS_DIR_PATH
from web.models.schain import SChainRecord
from tools.configs import SSL_CERTIFICATES_FILEPATH

TIMEOUT = 120


@pytest.fixture
def exiting_node(skale):
    cleanup_contracts(skale)
    SChainRecord.create_table()
    nodes = set_up_nodes(skale, 2)
    config = NodeConfig()
    config.id = nodes[0]['node_id']

    schain_name = generate_random_name()
    skale.manager.create_default_schain(schain_name)

    run_dkg_all(skale, schain_name, nodes)
    nodes.append(set_up_nodes(skale, 1)[0])

    exit_skale_lib = spawn_skale_lib(skale)
    exit_skale_lib.wallet = nodes[0]['wallet']

    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
    test_schain_path = os.path.join(SCHAINS_DIR_PATH, 'test')
    temp_schain_path = os.path.join(SCHAINS_DIR_PATH, '..', 'test')
    os.remove(key_path)
    os.remove(cert_path)
    shutil.move(test_schain_path, temp_schain_path)

    yield Node(exit_skale_lib, config), schain_name

    with open(cert_path, 'w') and open(key_path, 'w'):
        pass
    shutil.move(temp_schain_path, test_schain_path)

    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.delete_node_by_root(nodes[i]['node_id'], wait_for=True)


# TODO: Mock leaving history, check final exit status
def test_node_exit(skale, exiting_node):
    node = exiting_node[0]
    schain_name = exiting_node[1]
    spawn_skale_lib_mock = get_spawn_skale_mock(node.config.id)
    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock),\
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.creator.spawn_skale_lib', spawn_skale_lib_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(skale, node.config)
        node.exit({})

        wait_for_contract_exiting(skale, node.config.id)

        exit_status = node.get_exit_status()
        assert exit_status['status'] == NodeExitStatuses.WAIT_FOR_ROTATIONS.name
        assert exit_status['data'][0]['status'] == SchainExitStatuses.LEAVING.name

        wait_for_schain_alive(schain_name)

        monitor(skale, node.config)
        assert check_schain_alive(schain_name)

        finish_time = time()
        rotation_mock = {
            'result': True,
            'new_schain': False,
            'exiting_node': True,
            'finish_ts': finish_time,
            'rotation_id': 1
        }
        with mock.patch('core.schains.creator.check_for_rotation',
                        new=mock.Mock(return_value=rotation_mock)):
            monitor(skale, node.config)
            wait_for_schain_exiting(schain_name)
            cleaner_monitor(node.skale, node.config)
            checks = SChainChecks(schain_name, node.config.id).get_all()
            assert not checks['container']
            assert not checks['volume']
            assert not checks['data_dir']
            assert not checks['config']
