import subprocess
import time
from unittest import mock

import pytest
import os

from core.schains.checks import SChainChecks
from core.schains.process_manager import run_process_manager
from core.schains.cleaner import remove_schain_container, remove_schain_volume
from skale.utils.contracts_provision.main import cleanup_nodes_schains
from tests.rotation_test.utils import (set_up_rotated_schain, get_spawn_skale_mock,
                                       run_schain_container_mock, init_data_volume_mock,
                                       safe_run_dkg_mock, wait_for_schain_exiting,
                                       wait_for_schain_alive, wait_for_contract_exiting)
from tools.configs.schains import SCHAINS_DIR_PATH
from web.models.schain import SChainRecord


@pytest.fixture
def rotated_nodes(skale, schain_config, schain_db):
    cleanup_nodes_schains(skale)
    SChainRecord.create_table()

    schain_name = schain_config['skaleConfig']['sChain']['schainName']

    nodes, schain_name = set_up_rotated_schain(skale, schain_name)

    yield nodes, schain_name

    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.node_exit(nodes[i].config.id, wait_for=True)

    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    remove_schain_container(schain_name)
    remove_schain_volume(schain_name)
    # fix permission denied after schain container running
    subprocess.run(['rm', '-rf', schain_dir_path])


def test_new_node(skale, skale_ima, rotated_nodes, dutils):
    nodes, schain_name = rotated_nodes
    schain_record = SChainRecord.get_by_name(schain_name)
    exited_node, restarted_node = nodes[0], nodes[1]

    spawn_skale_lib_mock = get_spawn_skale_mock(restarted_node.config.id)

    with mock.patch('core.schains.monitor.add_firewall_rules'), \
            mock.patch('core.schains.monitor.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.monitor.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.monitor.safe_run_dkg', safe_run_dkg_mock), \
            mock.patch('core.schains.monitor.spawn_skale_manager_lib', spawn_skale_lib_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        run_process_manager(restarted_node.skale, skale_ima, restarted_node.config)
        wait_for_schain_alive(schain_name)

        exited_node.exit({})
        wait_for_contract_exiting(skale, exited_node.config.id)

        finish_time = time.time() + 10
        rotation_state_mock = {
            'in_progress': True,
            'new_schain': False,
            'exiting_node': False,
            'finish_ts': finish_time,
            'rotation_id': 1
        }
        with mock.patch('core.schains.monitor.get_rotation_state',
                        new=mock.Mock(return_value=rotation_state_mock)):
            run_process_manager(restarted_node.skale, skale_ima, restarted_node.config)
            wait_for_schain_exiting(schain_name, dutils)

        rotation_state_mock['in_progress'] = False
        with mock.patch('core.schains.monitor.remove_firewall_rules'), \
                mock.patch('core.schains.monitor.get_rotation_state',
                           new=mock.Mock(return_value=rotation_state_mock)):
            run_process_manager(restarted_node.skale, skale_ima, restarted_node.config)
            wait_for_schain_alive(schain_name)

            checks = SChainChecks(
                schain_name,
                restarted_node.config.id,
                schain_record=schain_record
            ).get_all()
            assert checks['container']
            assert checks['rpc']
