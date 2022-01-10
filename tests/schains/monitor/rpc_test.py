from time import sleep

from core.schains.monitor.rpc import monitor_schain_rpc
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import SChainRecord


def test_monitor_schain_rpc_no_container(schain_db, dutils, skaled_status):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)

    assert not monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils
    )
    assert not dutils.is_container_exists(container_name)


def test_monitor_schain_rpc_ec_0(schain_db, dutils, cleanup_schain_containers, skaled_status):
    schain_record = SChainRecord.get_by_name(schain_db)

    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_db)

    dutils.run_container(image_name=image_name, name=container_name, entrypoint='bash -c "exit 0"')
    sleep(7)
    schain_record.set_failed_rpc_count(100)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    assert not monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils
    )
    assert dutils.is_container_exists(container_name)

    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_monitor_schain_downloading_snapshot(
    schain_db,
    dutils,
    cleanup_schain_containers,
    skaled_status_downloading_snapshot
):
    schain_record = SChainRecord.get_by_name(schain_db)

    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_db)

    dutils.run_container(image_name=image_name, name=container_name, entrypoint='bash -c "exit 5"')
    sleep(7)
    schain_record.set_failed_rpc_count(100)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        skaled_status=skaled_status_downloading_snapshot,
        dutils=dutils
    )
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_monitor_schain_rpc_stuck_max_retries(
    schain_db,
    dutils,
    skaled_status,
    cleanup_schain_containers
):
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

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils
    )
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_monitor_schain_rpc_stuck(schain_db, dutils, cleanup_schain_containers, skaled_status):
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

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    assert schain_record.restart_count == 0
    monitor_schain_rpc(
        schain={'name': schain_db},
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils
    )
    assert schain_record.restart_count == 1
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] != finished_at
