import time
from unittest import mock

from core.chain.containers import monitor_skaled_container
from core.chain.runner import is_container_exists
from tests.utils import get_schain_struct, run_custom_schain_container
from web.models.schain import upsert_schain_record


def test_monitor_skaled_container(
    schain_db, skaled_status, dutils, ssl_folder, schain_config, cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = get_schain_struct(_test_schain_name=schain_db)

    monitor_skaled_container(schain.name, schain_record, skaled_status, dutils=dutils)
    assert not is_container_exists(schain_db, dutils=dutils)

    with mock.patch('core.chain.containers.is_volume_exists', return_value=True):
        monitor_skaled_container(schain.name, schain_record, skaled_status, dutils=dutils)
        assert is_container_exists(schain_db, dutils=dutils)


def test_monitor_skaled_container_exit_time_reached(
    schain_db,
    skaled_status_exit_time_reached,
    dutils,
    ssl_folder,
    schain_config,
    cleanup_schain_containers,
):
    schain_record = upsert_schain_record(schain_db)
    schain = get_schain_struct(_test_schain_name=schain_db)

    with mock.patch('core.chain.containers.is_volume_exists', return_value=True):
        schain_record.set_failed_rpc_count(100)
        schain_record.set_restart_count(100)
        monitor_skaled_container(
            schain.name, schain_record, skaled_status_exit_time_reached, dutils=dutils
        )
        assert len(dutils.get_all_schain_containers()) == 0
        assert schain_record.restart_count == 0
        assert schain_record.failed_rpc_count == 0

        monitor_skaled_container(
            schain.name,
            schain_record,
            skaled_status_exit_time_reached,
            abort_on_exit=False,
            dutils=dutils,
        )
        assert len(dutils.get_all_schain_containers()) == 1
        assert schain_record.restart_count == 0
        assert schain_record.failed_rpc_count == 0


def test_monitor_skaled_container_ec(
    schain_db, skaled_status, dutils, ssl_folder, schain_config, cleanup_schain_containers
):
    schain_record = upsert_schain_record(schain_db)
    schain = get_schain_struct(_test_schain_name=schain_db)

    run_custom_schain_container(dutils, schain.name, entrypoint=['sh', 'exit', '1'])
    # To make sure container initialized
    time.sleep(2)
    with mock.patch('core.chain.containers.is_volume_exists', return_value=True):
        schain_record.set_failed_rpc_count(100)
        schain_record.set_restart_count(0)
        monitor_skaled_container(schain.name, schain_record, skaled_status, dutils=dutils)
        assert schain_record.restart_count == 1
        assert schain_record.failed_rpc_count == 0


def test_monitor_skaled_container_rpc_proxy_needs_nginx(schain_db, skaled_status, dutils):
    schain_record = upsert_schain_record(schain_db)
    with (
        mock.patch('core.chain.containers.is_volume_exists', return_value=True),
        mock.patch('core.chain.containers.is_container_exists', return_value=False),
        mock.patch('core.chain.containers.run_skaled_container') as run_skaled,
        mock.patch('core.chain.containers.update_ssl_change_date'),
        mock.patch('core.nginx.mode.is_rpc_proxy_enabled', return_value=True),
    ):
        # without nginx the chain would have no public RPC, so skaled keeps the public ports
        with mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=False):
            assert monitor_skaled_container(schain_db, schain_record, skaled_status, dutils=dutils)
        assert run_skaled.call_args.kwargs['rpc_proxy'] is False
        assert schain_record.rpc_proxy_mode is False

        with mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=True):
            assert monitor_skaled_container(schain_db, schain_record, skaled_status, dutils=dutils)
        assert run_skaled.call_args.kwargs['rpc_proxy'] is True
        assert schain_record.rpc_proxy_mode is True

        # a public skaled cannot bind the ports nginx keeps
        with (
            mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=False),
            mock.patch('core.chain.containers.ChainProxyManager.remove', return_value=False),
        ):
            assert not monitor_skaled_container(
                schain_db, schain_record, skaled_status, dutils=dutils
            )
        assert run_skaled.call_count == 2
        assert schain_record.rpc_proxy_mode is True
