from time import sleep

from core.schains.monitor.rpc import monitor_schain_rpc
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import SChainRecord


def test_monitor_schain_rpc_no_container(caplog, schain_db, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    assert not monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        dutils=dutils
    )
    assert 'RPC monitor failed: container doesn\'t exit' in caplog.text


def test_monitor_schain_rpc_ec_0(caplog, schain_db, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)

    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_db)

    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "exit 0"'
    )
    sleep(10)

    assert not monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        dutils=dutils
    )
    assert 'container exited with zero, skipping RPC monitor' in caplog.text


def test_monitor_schain_rpc_stuck_max_retries(caplog, schain_db, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_db)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "exit 1000"'
    )

    schain_record.set_failed_rpc_count(100)
    schain_record.set_restart_count(100)

    monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        dutils=dutils
    )
    assert 'max restart count exceeded' in caplog.text


def test_monitor_schain_rpc_stuck(schain_db, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_db)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "exit 1000"'
    )

    schain_record.set_failed_rpc_count(100)
    schain_record.set_restart_count(0)

    assert schain_record.restart_count == 0
    monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        dutils=dutils
    )
    assert schain_record.restart_count == 1
