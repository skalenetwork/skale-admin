from core.schains.monitor import BaseMonitor


class BaseTestMonitor(BaseMonitor):
    @BaseMonitor._monitor_runner
    def run(self):
        return 1234


class CrashingTestMonitor(BaseMonitor):
    @BaseMonitor._monitor_runner
    def run(self):
        raise Exception('Something went wrong')


def test_base_monitor(schain_db, skale, node_config, schain_checks, schain_struct):
    test_monitor = BaseTestMonitor(
        skale=skale,
        schain=schain_struct,
        node_config=node_config,
        rotation_id=0,
        checks=schain_checks
    )
    assert test_monitor.run() == 1234


def test_crashing_monitor(schain_db, skale, node_config, schain_checks, capsys, schain_struct):
    test_monitor = CrashingTestMonitor(
        skale=skale,
        schain=schain_struct,
        node_config=node_config,
        rotation_id=0,
        checks=schain_checks
    )
    test_monitor.run()
    out, _ = capsys.readouterr()
    assert out == f'CrashingTestMonitor - schain: {schain_checks.name} - monitor runner failed\n'
