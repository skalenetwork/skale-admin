import subprocess
import time
from unittest import mock

import pytest
import os

from core.schains.checks import SChainChecks
from core.schains.creator import monitor
from core.schains.cleaner import remove_schain_container, remove_schain_volume
from tests.prepare_data import cleanup_contracts
from tests.rotation_test.utils import (set_up_rotated_schain, get_spawn_skale_mock,
                                       run_schain_container_mock, init_data_volume_mock,
                                       run_dkg_mock, wait_for_schain_exiting,
                                       wait_for_schain_alive, wait_for_contract_exiting)
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord

dutils = DockerUtils(volume_driver='local')


@pytest.fixture
def rotated_nodes(skale, schain_config, schain_db):
    cleanup_contracts(skale)
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


def test_new_node(skale, rotated_nodes):
    nodes, schain_name = rotated_nodes
    exited_node, restarted_node = nodes[0], nodes[1]

    spawn_skale_lib_mock = get_spawn_skale_mock(restarted_node.config.id)

    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock), \
            mock.patch('core.schains.creator.spawn_skale_manager_lib', spawn_skale_lib_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(restarted_node.skale, restarted_node.config)
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
        with mock.patch('core.schains.creator.get_rotation_state',
                        new=mock.Mock(return_value=rotation_state_mock)):
            monitor(restarted_node.skale, restarted_node.config)
            wait_for_schain_exiting(schain_name)

        rotation_state_mock['in_progress'] = False
        with mock.patch('core.schains.creator.remove_firewall_rules'), \
                mock.patch('core.schains.creator.get_rotation_state',
                           new=mock.Mock(return_value=rotation_state_mock)):
            monitor(restarted_node.skale, restarted_node.config)
            wait_for_schain_alive(schain_name)
            checks = SChainChecks(schain_name, restarted_node.config.id).get_all()
            assert checks['container']
            assert checks['rpc']
