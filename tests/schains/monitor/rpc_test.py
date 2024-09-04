import datetime
import json
import mock
from time import sleep

import freezegun
import requests

from core.schains.monitor.rpc import handle_failed_schain_rpc
from core.schains.runner import get_container_info
from core.schains.rpc import check_endpoint_blocks
from tools.configs.containers import SCHAIN_CONTAINER
from web.models.schain import SChainRecord
from tests.utils import get_schain_struct

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


def test_handle_failed_schain_rpc_no_container(schain_db, dutils, skaled_status):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)

    assert not handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils,
    )
    assert not dutils.is_container_exists(container_name)


def test_handle_failed_schain_rpc_exit_time_reached(
    schain_db, dutils, cleanup_schain_containers, skaled_status_exit_time_reached
):
    schain_record = SChainRecord.get_by_name(schain_db)

    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)

    dutils.run_container(image_name=image_name, name=container_name, entrypoint='bash -c "exit 0"')
    sleep(7)
    schain_record.set_failed_rpc_count(100)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    assert not handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status_exit_time_reached,
        dutils=dutils,
    )
    assert dutils.is_container_exists(container_name)

    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_monitor_schain_downloading_snapshot(
    schain_db, dutils, cleanup_schain_containers, skaled_status_downloading_snapshot
):
    schain_record = SChainRecord.get_by_name(schain_db)

    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)

    dutils.run_container(
        image_name=image_name, name=container_name, entrypoint='bash -c "sleep 100"'
    )
    sleep(7)
    schain_record.set_failed_rpc_count(100)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status_downloading_snapshot,
        dutils=dutils,
    )
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_handle_failed_schain_rpc_stuck_max_retries(
    schain_db, dutils, skaled_status, cleanup_schain_containers
):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)
    dutils.run_container(
        image_name=image_name, name=container_name, entrypoint='bash -c "sleep 100"'
    )

    schain_record.set_failed_rpc_count(100)
    schain_record.set_restart_count(100)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils,
    )
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_monitor_container_exited(schain_db, dutils, cleanup_schain_containers, skaled_status):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)
    dutils.run_container(
        image_name=image_name, name=container_name, entrypoint='bash -c "exit 100;"'
    )

    schain_record.set_failed_rpc_count(100)
    schain_record.set_restart_count(0)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    assert schain_record.restart_count == 0
    handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils,
    )
    assert schain_record.restart_count == 0
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] == finished_at


def test_handle_failed_schain_rpc_stuck(
    schain_db, dutils, cleanup_schain_containers, skaled_status
):
    schain_record = SChainRecord.get_by_name(schain_db)
    image_name, container_name, _, _ = get_container_info(SCHAIN_CONTAINER, schain_db)
    dutils.run_container(
        image_name=image_name, name=container_name, entrypoint='bash -c "sleep 100"'
    )

    schain_record.set_failed_rpc_count(100)
    schain_record.set_restart_count(0)

    container_info = dutils.get_info(container_name)
    finished_at = container_info['stats']['State']['FinishedAt']

    assert schain_record.restart_count == 0
    handle_failed_schain_rpc(
        schain=get_schain_struct(schain_name=schain_db),
        schain_record=schain_record,
        skaled_status=skaled_status,
        dutils=dutils,
    )
    assert schain_record.restart_count == 1
    container_info = dutils.get_info(container_name)
    assert container_info['stats']['State']['FinishedAt'] != finished_at


@mock.patch('tools.helper.requests.post')
@freezegun.freeze_time(CURRENT_DATETIME)
def test_check_endpoint_blocks(post_request_mock):
    endpoint = 'http://127.0.0.1:10003'

    post_request_mock.side_effect = requests.exceptions.RequestException('Test error')
    assert check_endpoint_blocks(endpoint) is False
    post_request_mock.side_effect = None

    response_dummy = mock.Mock()
    post_request_mock.return_value = response_dummy

    response_dummy.json = mock.Mock(return_value={})
    assert check_endpoint_blocks(endpoint) is False

    response_dummy.json = mock.Mock(
        side_effect=json.JSONDecodeError('Test error', doc='doc', pos=1)
    )
    assert check_endpoint_blocks(endpoint) is False

    response_dummy.json = mock.Mock(return_value={'result': {'timestamp': '0xhhhhh'}})
    assert check_endpoint_blocks(endpoint) is False

    response_dummy.json = mock.Mock(return_value={'result': {'timestamp': '0x1'}})
    assert check_endpoint_blocks(endpoint) is False

    hex_offset_ts = hex(CURRENT_TIMESTAMP + 1)
    response_dummy.json = mock.Mock(return_value={'result': {'timestamp': hex_offset_ts}})
    assert check_endpoint_blocks(endpoint) is True
