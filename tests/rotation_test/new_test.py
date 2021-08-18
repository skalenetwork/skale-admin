import shutil
from unittest import mock

import pytest
import os

from core.schains.monitor import monitor_schain
from core.schains.checks import SChainChecks
from skale.utils.contracts_provision.main import cleanup_nodes_schains
from tests.rotation_test.utils import (
    set_up_rotated_schain,
    wait_for_contract_exiting,
    init_data_volume_mock, run_dkg_mock
)
from tools.configs.schains import SCHAINS_DIR_PATH
from web.models.schain import SChainRecord


@pytest.fixture
def rotated_nodes(skale, schain_config, schain_db, cert_key_pair, dutils):
    cleanup_nodes_schains(skale)
    SChainRecord.create_table()
    schain_name = schain_config['skaleConfig']['sChain']['schainName']

    nodes, schain_name = set_up_rotated_schain(skale, schain_name)

    yield nodes, schain_name

    shutil.rmtree(os.path.join(SCHAINS_DIR_PATH, schain_name))
    dutils.safe_rm(f'skale_schain_{schain_name}', force=True)
    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.node_exit(nodes[i].config.id, wait_for=True)


def test_new_node(skale, skale_ima, rotated_nodes, dutils):
    nodes, schain_name = rotated_nodes

    exited_node, new_node = nodes[0], nodes[2]
    exited_node.exit({})

    wait_for_contract_exiting(skale, exited_node.config.id)

    with mock.patch('core.schains.monitor.add_firewall_rules'), \
            mock.patch(
                'core.schains.monitor.init_data_volume',
                init_data_volume_mock
    ), \
            mock.patch('core.schains.monitor.run_dkg', run_dkg_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):

        ecdsa_sgx_key_name = new_node.config.sgx_key_name
        node_info = new_node.config.all()
        schain = skale.schains.get_by_name(schain_name)

        monitor_schain(
            new_node.skale,
            skale_ima,
            node_info=node_info,
            schain=schain,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            dutils=dutils
        )
        checks = SChainChecks(
            schain_name,
            new_node.config.id,
            dutils=dutils
        ).get_all()
        assert checks['container']
        assert checks['volume']
        assert checks['data_dir']
        assert checks['config']
