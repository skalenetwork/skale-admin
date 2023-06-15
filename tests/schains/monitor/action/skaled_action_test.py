import datetime
import json
import os
import time

import freezegun
import pytest
import mock

from core.schains.checks import SkaledChecks
from core.schains.cleaner import remove_ima_container
from core.schains.config.directory import new_config_filename, schain_config_dir
from core.schains.monitor.action import SkaledActionManager
from core.schains.rotation import get_schain_public_key
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from web.models.schain import SChainRecord

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


def run_ima_container_mock(schain: dict, mainnet_chain_id: int, dutils=None):
    image_name, container_name, _, _ = get_container_info(
        IMA_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


def monitor_schain_container_mock(
    schain,
    schain_record,
    skaled_status,
    public_key=None,
    start_ts=None,
    dutils=None
):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def skaled_checks(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecks(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        ima_linked=True,
        dutils=dutils
    )


@pytest.fixture
def skaled_am(
    schain_db,
    skale,
    node_config,
    rule_controller,
    schain_on_contracts,
    predeployed_ima,
    rotation_data,
    secret_key,
    ima_data,
    ssl_folder,
    dutils,
    skaled_checks
):
    name = schain_db
    finish_ts = skale.node_rotation.get_schain_finish_ts(
      node_id=rotation_data['leaving_node'],
      schain_name=name
    )
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)
    public_key = get_schain_public_key(skale, name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        ima_data=ima_data,
        public_key=public_key,
        finish_ts=finish_ts,
        checks=skaled_checks,
        dutils=dutils
    )


# def test_skaled_actions(skaled_am, skaled_checks, cleanup_schain_containers):
#     try:
#         skaled_am.firewall_rules()
#         assert skaled_checks.firewall_rules
#         skaled_am.volume()
#         assert skaled_checks.volume
#         skaled_am.skaled_container()
#         assert skaled_checks.skaled_container
#         skaled_am.ima_container()
#         assert skaled_checks.ima_container
#         # Try to create already created volume
#         skaled_am.volume()
#         assert skaled_checks.volume
#         # Try to create already created container
#         skaled_am.skaled_container()
#         assert skaled_checks.skaled_container
#     finally:
#         skaled_am.cleanup_schain_docker_entity()
#
#
# def test_skaled_restart_reload_actions(skaled_am, skaled_checks, cleanup_schain_containers):
#     try:
#         skaled_am.volume()
#         assert skaled_checks.volume
#         skaled_am.skaled_container()
#         skaled_am.reloaded_skaled_container()
#         assert skaled_checks.skaled_container
#     finally:
#         skaled_am.cleanup_schain_docker_entity()


def test_volume_action(skaled_am, skaled_checks):
    try:
        assert not skaled_checks.volume
        skaled_am.volume()
        assert skaled_checks.volume
        skaled_am.volume()
        assert skaled_checks.volume
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_action(skaled_am, skaled_checks):
    try:
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            monitor_schain_container_mock
        ):
            skaled_am.volume()
            assert not skaled_checks.skaled_container
            skaled_am.skaled_container()
            assert skaled_checks.skaled_container
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_with_snapshot_action(skaled_am):
    try:
        skaled_am.volume()
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            new=mock.Mock()
        ) as monitor_schain_mock:
            skaled_am.skaled_container(download_snapshot=True)

        monitor_schain_mock.assert_called_with(
            skaled_am.schain,
            schain_record=skaled_am.schain_record,
            skaled_status=skaled_am.skaled_status,
            public_key='0:0:1:0',
            start_ts=None,
            dutils=skaled_am.dutils
        )
        assert monitor_schain_mock.call_count == 1
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_snapshot_delay_start_action(skaled_am):
    try:
        skaled_am.volume()
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            new=mock.Mock()
        ) as monitor_schain_mock:
            skaled_am.finish_ts = 1245
            skaled_am.skaled_container(download_snapshot=True, delay_start=True)

        monitor_schain_mock.assert_called_with(
            skaled_am.schain,
            schain_record=skaled_am.schain_record,
            skaled_status=skaled_am.skaled_status,
            public_key='0:0:1:0',
            start_ts=1245,
            dutils=skaled_am.dutils
        )
        assert monitor_schain_mock.call_count == 1
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_restart_skaled_container_action(skaled_am, skaled_checks):
    skaled_am.reloaded_skaled_container()
    try:
        skaled_am.volume()
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            monitor_schain_container_mock
        ):
            assert not skaled_checks.skaled_container
            skaled_am.restart_skaled_container()
            assert skaled_checks.skaled_container
            skaled_am.restart_skaled_container()
            assert skaled_checks.skaled_container
            skaled_am.reloaded_skaled_container()
            assert skaled_checks.skaled_container
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_ima_container_action(skaled_am, skaled_checks, schain_config, predeployed_ima):
    try:
        skaled_am.ima_data.linked = True
        with mock.patch(
            'core.schains.monitor.containers.run_ima_container',
            run_ima_container_mock
        ):
            assert not skaled_checks.ima_container
            skaled_am.ima_container()
            assert skaled_checks.ima_container
            skaled_am.ima_container()
            assert skaled_checks.ima_container
    finally:
        remove_ima_container(skaled_am.name, dutils=skaled_am.dutils)


def test_cleanup_empty_action(skaled_am, skaled_checks):
    skaled_am.cleanup_schain_docker_entity()
    assert not skaled_checks.skaled_container


def test_schain_finish_ts(skale, schain_on_contracts):
    name = schain_on_contracts
    max_node_id = skale.nodes.get_nodes_number() - 1
    assert skale.node_rotation.get_schain_finish_ts(max_node_id, name) is None


def test_display_skaled_logs(skale, skaled_am, _schain_name):
    skaled_am.log_executed_blocks()
    # Don't display if no container
    skaled_am.display_skaled_logs()
    try:
        skaled_am.volume()
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            monitor_schain_container_mock
        ):
            skaled_am.skaled_container()
    finally:
        skaled_am.display_skaled_logs()
        skaled_am.cleanup_schain_docker_entity()


@freezegun.freeze_time(CURRENT_DATETIME)
def test_upd_schain_record(skaled_am, skaled_checks):
    # Prepare fake record
    r = SChainRecord.get_by_name(skaled_am.name)
    r.set_restart_count(1)
    r.set_failed_rpc_count(1)

    assert r.monitor_last_seen != CURRENT_DATETIME
    skaled_am._upd_last_seen()
    r = SChainRecord.get_by_name(skaled_am.name)
    assert r.monitor_last_seen == CURRENT_DATETIME
    skaled_am._upd_schain_record()
    r = SChainRecord.get_by_name(skaled_am.name)

    assert not r.first_run
    assert not r.new_schain
    r.restart_count == 0
    r.failed_rpc_count == 0


def test_update_config(skaled_am, skaled_checks):
    folder = schain_config_dir(skaled_am.name)
    config_path = os.path.join(folder, f'schain_{skaled_am.name}.json')
    os.remove(config_path)

    assert not skaled_checks.config
    assert not skaled_checks.config_updated
    upstream_path = os.path.join(folder, new_config_filename(skaled_am.name, rotation_id=5))
    config_content = {'config': 'mock_v5'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)
    skaled_am.update_config()
    with open(config_path) as config_file:
        json.load(config_file) == config_content
    assert skaled_checks.config
    assert skaled_checks.config_updated

    time.sleep(1)
    upstream_path = os.path.join(folder, new_config_filename(skaled_am.name, rotation_id=6))
    config_content = {'config': 'mock_v6'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)

    assert skaled_checks.config
    assert not skaled_checks.config_updated
    skaled_am.update_config()

    assert skaled_checks.config_updated