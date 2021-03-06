import subprocess
import time
from unittest import mock

import pytest
import os

from tests.rotation_test.utils import (wait_for_contract_exiting, wait_for_schain_alive,
                                       wait_for_schain_exiting, check_schain_alive,
                                       get_spawn_skale_mock, set_up_rotated_schain, run_dkg_mock,
                                       init_data_volume_mock, run_schain_container_mock,
                                       delete_bls_keys_mock)

from core.node import NodeExitStatuses, SchainExitStatuses
from core.schains.checks import SChainChecks
from core.schains.cleaner import (monitor as cleaner_monitor,
                                  remove_schain_container,
                                  remove_schain_volume)
from core.schains.creator import monitor
from skale.utils.contracts_provision.main import cleanup_nodes_schains
from tools.configs.schains import SCHAINS_DIR_PATH


@pytest.fixture
def exiting_node(skale, db):
    cleanup_nodes_schains(skale)

    nodes, schain_name = set_up_rotated_schain(skale)
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)

    yield nodes, schain_name

    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.node_exit(nodes[i].config.id, wait_for=True)

    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    remove_schain_container(schain_name)
    remove_schain_volume(schain_name)
    # fix permission denied after schain container running
    subprocess.run(['rm', '-rf', schain_dir_path])


# TODO: Mock leaving history, check final exit status
def test_node_exit(skale, exiting_node):
    nodes, schain_name = exiting_node
    node = nodes[0]
    spawn_skale_lib_mock = get_spawn_skale_mock(node.config.id)
    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock),\
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.creator.spawn_skale_manager_lib', spawn_skale_lib_mock), \
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

        finish_time = time.time()
        rotation_state_mock = {
            'in_progress': True,
            'new_schain': False,
            'exiting_node': True,
            'finish_ts': finish_time,
            'rotation_id': 1
        }
        with mock.patch('core.schains.creator.get_rotation_state',
                        new=mock.Mock(return_value=rotation_state_mock)),\
                mock.patch('core.schains.cleaner.SgxClient.delete_bls_key', delete_bls_keys_mock):
            monitor(skale, node.config)
            wait_for_schain_exiting(schain_name)
            cleaner_monitor(node.skale, node.config)
            checks = SChainChecks(schain_name, node.config.id).get_all()
            assert not checks['container']
            assert not checks['volume']
            assert not checks['data_dir']
            assert not checks['config']
