from core.schains.monitor import RegularMonitor


def test_regular_monitor(schain_db, skale, node_config, schain_checks, schain_on_contracts):
    test_monitor = RegularMonitor(
        skale=skale,
        schain=schain_on_contracts,
        node_config=node_config,
        rotation_id=0,
        checks=schain_checks
    )
    test_monitor.run()
    # todo: improve test
