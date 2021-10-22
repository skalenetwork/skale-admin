import logging

import pytest
from core.schains.monitor import RegularMonitor

logger = logging.getLogger(__name__)


def add_firewall_rules_mock(name):
    pass


class TestRegularMonitor(RegularMonitor):
    def firewall_rules(self, overwrite) -> None:
        if not self.checks.firewall_rules.status or overwrite:
            add_firewall_rules_mock(self.name)
        else:
            logger.info(f'{self.p} firewall_rules - ok')


def test_regular_monitor(schain_db, skale, node_config, schain_checks, schain_on_contracts):
    # todo: use existing chain here!
    test_monitor = TestRegularMonitor(
        skale=skale,
        schain=schain_on_contracts,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks
    )
    test_monitor.run()
    # todo: improve test


@pytest.mark.skip('not ready yet')
def test_regular_monitor_new_chain(schain_db, skale, node_config, schain_checks,
                                   schain_on_contracts):
    # todo: create 2 nodes chain on contracts
    # todo: emulate dkg for the second node
    # todo: run monitor for the first node

    test_monitor = TestRegularMonitor(
        skale=skale,
        schain=schain_on_contracts,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks
    )
    test_monitor.run()
