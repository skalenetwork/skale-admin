import pytest

from core.schains.monitor import BaseMonitor


class BaseTestMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        return 1234

    def _run_all_checks(self):
        pass


class CrashingTestMonitor(BaseMonitor):
    @BaseMonitor.monitor_runner
    def run(self):
        raise Exception('Something went wrong')

    def _run_all_checks(self):
        pass


def test_base_monitor(schain_db, skale, node_config, schain_checks, skale_ima, schain_struct):
    test_monitor = BaseTestMonitor(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain_struct,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks
    )
    assert test_monitor.run() == 1234


def test_crashing_monitor(schain_db, skale, node_config, schain_checks, skale_ima, schain_struct):
    test_monitor = CrashingTestMonitor(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain_struct,
        node_config=node_config,
        rotation_data={'rotation_id': 1},
        checks=schain_checks
    )
    with pytest.raises(Exception):
        test_monitor.run()
