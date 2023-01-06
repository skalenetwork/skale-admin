import datetime

import mock
import freezegun
from skale.schain_config.generator import get_nodes_for_schain

from core.schains.monitor.containers import monitor_schain_container, schedule_exit
from core.schains.runner import is_container_exists
from web.models.schain import upsert_schain_record

from tests.schains.monitor.main_test import run_exited_schain_container
from tests.utils import request_mock, response_mock

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


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


def test_monitor_schain_container_ec(
    schain_db,
    skaled_status,
    dutils,
    ssl_folder,
    schain_config,
    cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = {'name': schain_db, 'partOfNode': 0, 'generation': 0}

    run_exited_schain_container(dutils, schain_db, 123)
    with mock.patch('core.schains.monitor.containers.is_volume_exists', return_value=True):
        schain_record.set_failed_rpc_count(100)
        schain_record.set_restart_count(0)
        monitor_schain_container(
            schain,
            schain_record,
            skaled_status,
            dutils=dutils
        )
        assert schain_record.restart_count == 1
        assert schain_record.failed_rpc_count == 0


def test_monitor_schain_container_ec_0(
    schain_db,
    skaled_status,
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
        schain_record.set_restart_count(0)
        monitor_schain_container(
            schain,
            schain_record,
            skaled_status,
            dutils=dutils
        )
        assert schain_record.restart_count == 0
        assert schain_record.failed_rpc_count == 100


@freezegun.freeze_time(CURRENT_DATETIME)
def test_schedule_exit(
    skale,
    node_config,
    schain_config,
    schain_on_contracts,
):
    schain_name = schain_on_contracts
    node_id = node_config.id
    schain_nodes = get_nodes_for_schain(skale, schain_name)

    post_mock = request_mock(response_mock(json_data={}))
    with mock.patch('core.schains.monitor.containers.requests.post',
                    post_mock):
        schedule_exit(schain_name, schain_nodes, node_id)
        post_mock.assert_called_with(
            url='http://127.0.0.1:10003',
            data='{"id": 0, "jsonrpc": "2.0", "method": "setSchainExitTime", "params": {"finishTime": 1594903500}}',  # noqa
            headers={'content-type': 'application/json'}
        )
