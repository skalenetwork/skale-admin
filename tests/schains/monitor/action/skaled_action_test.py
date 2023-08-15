import datetime
import json
import os
import time

import freezegun
import pytest
import mock

from core.schains.checks import SkaledChecks
from core.schains.cleaner import remove_ima_container
from core.schains.config.directory import schain_config_dir
from core.schains.config.file_manager import UpstreamConfigFilename
from core.schains.firewall.types import SChainRule
from core.schains.monitor.action import SkaledActionManager
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from web.models.schain import SChainRecord

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


def run_ima_container_mock(schain: dict, mainnet_chain_id: int, image: str, dutils=None):
    image_name, container_name, _, _ = get_container_info(
        IMA_CONTAINER, schain['name'])
    image = image or image_name
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


def monitor_schain_container_mock(
    schain,
    schain_record,
    skaled_status,
    download_snapshot=False,
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
    secret_key,
    ssl_folder,
    dutils,
    skaled_checks
):
    name = schain_db
    schain = skale.schains.get_by_name(name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        checks=skaled_checks,
        node_config=node_config,
        dutils=dutils
    )


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
            download_snapshot=True,
            start_ts=None,
            dutils=skaled_am.dutils
        )
        assert monitor_schain_mock.call_count == 1
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_snapshot_delay_start_action(skaled_am):
    ts = int(time.time())
    try:
        skaled_am.volume()
        with mock.patch(
            'core.schains.monitor.action.monitor_schain_container',
            new=mock.Mock()
        ) as monitor_schain_mock:
            skaled_am.skaled_container(download_snapshot=True, start_ts=ts)

        monitor_schain_mock.assert_called_with(
            skaled_am.schain,
            schain_record=skaled_am.schain_record,
            skaled_status=skaled_am.skaled_status,
            download_snapshot=True,
            start_ts=ts,
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


@pytest.fixture
def cleanup_ima(dutils, skaled_am):
    try:
        yield
    finally:
        remove_ima_container(skaled_am.name, dutils=dutils)


@pytest.fixture
def ima_linked(econfig):
    state = econfig.get()
    state.ima_linked = True
    econfig.update(state)


def test_ima_container_action_new_chain(
    skaled_am,
    skaled_checks,
    schain_config,
    predeployed_ima,
    ima_linked,
    cleanup_ima,
    dutils
):
    with mock.patch(
        'core.schains.monitor.containers.run_ima_container',
        run_ima_container_mock
    ):
        skaled_am.ima_container()
        containers = dutils.get_all_ima_containers(all=True)
        assert len(containers) == 1
        container_name = containers[0].name
        assert container_name == f'skale_ima_{skaled_am.name}'
        image = dutils.get_container_image_name(container_name)
        assert image == 'skalenetwork/ima:2.0.0-develop.3'


@mock.patch('core.schains.monitor.containers.run_ima_container', run_ima_container_mock)
def test_ima_container_action_old_chain(
    skaled_am,
    skaled_checks,
    schain_config,
    predeployed_ima,
    ima_linked,
    cleanup_ima,
    dutils
):
    ts = int(time.time())
    mts = ts + 3600
    with mock.patch('core.schains.monitor.action.get_ima_migration_ts', return_value=mts):
        skaled_am.ima_container()
        containers = dutils.get_all_ima_containers(all=True)
        assert len(containers) == 1
        assert containers[0].name == f'skale_ima_{skaled_am.name}'
        container_name = containers[0].name
        assert container_name == f'skale_ima_{skaled_am.name}'
        image = dutils.get_container_image_name(container_name)
        assert image == 'skalenetwork/ima:2.0.0-develop.3'
        assert dutils.pulled('skalenetwork/ima:2.0.0-develop.12')

    mts = ts - 5
    with mock.patch('core.schains.monitor.action.get_ima_migration_ts', return_value=mts):
        skaled_am.ima_container()
        containers = dutils.get_all_ima_containers(all=True)
        assert len(containers) == 1
        container_name = containers[0].name
        assert container_name == f'skale_ima_{skaled_am.name}'
        image = dutils.get_container_image_name(container_name)
        assert image == 'skalenetwork/ima:2.0.0-develop.12'


def test_ima_container_action_not_linked(
    skaled_am,
    skaled_checks,
    schain_db,
    _schain_name,
    cleanup_ima_containers,
    dutils
):
    skaled_am.ima_container()
    assert skaled_checks.ima_container


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
    upstream_path = UpstreamConfigFilename(
        skaled_am.name, rotation_id=5, ts=int(time.time())).abspath(folder)

    config_content = {'config': 'mock_v5'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)
    skaled_am.update_config()
    with open(config_path) as config_file:
        json.load(config_file) == config_content
    assert skaled_checks.config
    assert skaled_checks.config_updated

    time.sleep(1)
    upstream_path = UpstreamConfigFilename(
        skaled_am.name, rotation_id=6, ts=int(time.time())).abspath(folder)

    config_content = {'config': 'mock_v6'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)

    assert skaled_checks.config
    assert not skaled_checks.config_updated
    skaled_am.update_config()

    assert skaled_checks.config_updated


def test_firewall_rules_action(skaled_am, skaled_checks, rule_controller, econfig):
    assert not skaled_checks.firewall_rules
    skaled_am.firewall_rules()
    assert skaled_checks.firewall_rules
    added_rules = list(rule_controller.firewall_manager.rules)
    print(added_rules)
    assert added_rules == [
        SChainRule(port=10000, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(port=10001, first_ip='1.1.1.1', last_ip='2.2.2.2'),
        SChainRule(port=10001, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10002),
        SChainRule(port=10003),
        SChainRule(port=10004, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(port=10005, first_ip='1.1.1.1', last_ip='2.2.2.2'),
        SChainRule(port=10005, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(port=10005, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10007),
        SChainRule(port=10008),
        SChainRule(port=10009),
        SChainRule(port=10010, first_ip='127.0.0.2', last_ip='127.0.0.2')
    ]
