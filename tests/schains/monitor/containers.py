import mock

from core.schains.monitor.containers import monitor_schain_container
from core.schains.runner import is_container_exists
from web.models.schain import upsert_schain_record

from tests.schains.monitor.main_test import run_exited_schain_container


def test_monitor_schain_container(
    schain_db,
    skaled_status,
    dutils,
    ssl_folder,
    schain_config,
    cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = {'name': schain_db, 'partOfNode': 0, 'generation': 0}

    monitor_schain_container(schain, schain_record, skaled_status, dutils=dutils)
    assert not is_container_exists(schain_db, dutils=dutils)

    with mock.patch('core.schains.monitor.containers.is_volume_exists', return_value=True):
        monitor_schain_container(schain, schain_record, skaled_status, dutils=dutils)
        assert is_container_exists(schain_db, dutils=dutils)


def test_monitor_schain_container_exit_time_reached(
    schain_db,
    skaled_status_exit_time_reached,
    dutils,
    ssl_folder,
    schain_config,
    cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = {'name': schain_db, 'partOfNode': 0, 'generation': 0}

    run_exited_schain_container(dutils, schain_db, 0)
    with mock.patch('core.schains.monitor.containers.is_volume_exists', return_value=True):
        schain_record.set_failed_rpc_count(100)
        schain_record.set_restart_count(100)
        monitor_schain_container(
            schain,
            schain_record,
            skaled_status_exit_time_reached,
            dutils=dutils
        )
        assert schain_record.restart_count == 0
        assert schain_record.failed_rpc_count == 0


def test_monitor_schain_container_cleanup(
    schain_db,
    skaled_status_repair,
    dutils,
    ssl_folder,
    schain_config,
    cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = {'name': schain_db, 'partOfNode': 0, 'generation': 0}

    run_exited_schain_container(dutils, schain_db, 0)
    with mock.patch('core.schains.monitor.containers.is_volume_exists', return_value=True):
        schain_record.set_failed_rpc_count(100)
        schain_record.set_restart_count(100)
        monitor_schain_container(
            schain,
            schain_record,
            skaled_status_repair,
            dutils=dutils
        )
        assert schain_record.restart_count == 0
        assert schain_record.failed_rpc_count == 0
