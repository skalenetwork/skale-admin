import shutil
from unittest import mock

import pytest
import os

from core.schains.checks import SChainChecks
from core.schains.creator import monitor
from tests.rotation_test.three_nodes.utils import (
    wait_for_contract_exiting,
    init_data_volume_mock, run_dkg_mock
)
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord

from tests.rotation_test.five_nodes.utils import set_up_schain_on_contracts, run_schain_containers

dutils = DockerUtils(volume_driver='local')


@pytest.fixture
def rotated_schain(skale):
    SChainRecord.create_table()

    nodes, schain_name = set_up_schain_on_contracts(skale)
    run_schain_containers()

    yield nodes, schain_name

    shutil.rmtree(os.path.join(SCHAINS_DIR_PATH, schain_name))
    dutils.safe_rm(f'skale_schain_{schain_name}', force=True)
    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 5):
        skale.manager.delete_node_by_root(nodes[i].config.id, wait_for=True)


def test_new_node(skale, rotated_schain):
    nodes, schain_name = rotated_schain
    exited_node, new_node = nodes[0], nodes[4]
    exited_node.exit({})

    wait_for_contract_exiting(skale, exited_node.config.id)

    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_schain_container'), \
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(new_node.skale, new_node.config)
        checks = SChainChecks(schain_name, new_node.config.id).get_all()
        assert checks['container']
        assert checks['volume']
        assert checks['data_dir']
        assert checks['config']