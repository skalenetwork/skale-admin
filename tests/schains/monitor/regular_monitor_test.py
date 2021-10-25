import logging

from unittest import mock

from core.schains.monitor import RegularMonitor
from tests.rotation_test.utils import (
    init_data_volume_mock, run_dkg_mock
)

logger = logging.getLogger(__name__)


def test_regular_monitor(schain_db, skale, node_config, schain_checks, schain_on_contracts,
                         skale_ima, dutils, ssl_folder):
    with mock.patch('core.schains.monitor.base_monitor.add_firewall_rules'), \
        mock.patch(
            'core.schains.monitor.base_monitor.init_data_volume',
            init_data_volume_mock
        ), \
        mock.patch('core.schains.dkg.run_dkg', run_dkg_mock), \
        mock.patch('core.schains.checks.apsent_iptables_rules',
                   new=mock.Mock(return_value=[True, True])):

        schain_name = schain_on_contracts
        schain_struct = {
            'name': schain_name,
            'partOfNode': 0,
        }
        test_monitor = RegularMonitor(
            skale=skale,
            skale_ima=skale_ima,
            schain=schain_struct,
            node_config=node_config,
            rotation_data={'rotation_id': 0},
            checks=schain_checks,
            dutils=dutils
        )
        test_monitor.run()
