import datetime
import json
import os
import time
from typing import Optional
from unittest import mock

import freezegun
import pytest
from skale.types.schain import SchainName, SchainStructure

from core.chain.runner import get_container_info
from core.chain.status import SkaledStatus
from core.checks.schain import SkaledChecks
from core.config.schain.directory import schain_config_dir
from core.config.schain.file_manager import UpstreamConfigFilename
from core.firewall import LOOPBACK_INTERFACE, Action, IRuleController, SChainRule
from core.monitor.schain.action_skaled import SkaledActionManager
from core.node_config import NodeConfig
from core.schains.cleaner import remove_ima_container
from core.schains.external_config import ExternalConfig
from core.types.chain import ChainName
from tests.utils import IMA_MIGRATION_TS, TEST_TASK_SLEEP
from tools.constants.containers import SKALED_CONTAINER
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


def monitor_skaled_container_mock(
    chain_name: ChainName,
    chain_record: SChainRecord,
    skaled_status: SkaledStatus,
    download_snapshot=False,
    start_ts=None,
    snapshot_from: Optional[str] = None,
    abort_on_exit: bool = True,
    dutils: Optional[DockerUtils] = None,
    passive_node: bool = False,
    historic_state: bool = False,
    part_of_node: Optional[int] = None,
):
    if dutils is None:
        dutils = DockerUtils()
    image_name, container_name, _, _ = get_container_info(SKALED_CONTAINER, chain_name)
    dutils.safe_rm(container_name)
    if not skaled_status.exit_time_reached or not abort_on_exit:
        dutils.run_container(
            image_name=image_name,
            name=container_name,
            entrypoint='bash -c "while true; do foo; sleep 2; done"',
        )


@pytest.fixture
def skaled_checks(
    schain_structure: SchainStructure, rule_controller: IRuleController, dutils: DockerUtils
):
    schain_record = SChainRecord.get_by_name(schain_structure.name)
    return SkaledChecks(
        schain_name=schain_structure.name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils,
        passive_node=False,
    )


@pytest.fixture
def skaled_am(
    schain_structure: SchainStructure,
    node_config: NodeConfig,
    rule_controller: IRuleController,
    secret_key,
    ssl_folder,
    ima_migration_schedule,
    ncli_status,
    dutils,
    skaled_checks,
):
    return SkaledActionManager(
        schain=schain_structure,
        rule_controller=rule_controller,
        checks=skaled_checks,
        node_config=node_config,
        ncli_status=ncli_status,
        dutils=dutils,
        post_run_delay=TEST_TASK_SLEEP,
        schain_cleanup_timeout=TEST_TASK_SLEEP,
    )


def test_volume_action(skaled_am: SkaledActionManager, skaled_checks: SkaledChecks):
    try:
        assert not skaled_checks.volume
        skaled_am.volume()
        assert skaled_checks.volume
        skaled_am.volume()
        assert skaled_checks.volume
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_action(skaled_am: SkaledActionManager, skaled_checks: SkaledChecks):
    try:
        with mock.patch(
            'core.monitor.schain.action_skaled.monitor_skaled_container',
            monitor_skaled_container_mock,
        ):
            skaled_am.volume()
            assert not skaled_checks.skaled_container
            skaled_am.skaled_container()
            assert skaled_checks.skaled_container
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_with_snapshot_action(skaled_am: SkaledActionManager):
    try:
        skaled_am.volume()
        with mock.patch(
            'core.monitor.schain.action_skaled.monitor_skaled_container', new=mock.Mock()
        ) as monitor_skaled_container_mock:
            skaled_am.skaled_container(download_snapshot=True)

        monitor_skaled_container_mock.assert_called_with(
            skaled_am.schain.name,
            chain_record=skaled_am.chain_record,
            skaled_status=skaled_am.skaled_status,
            download_snapshot=True,
            snapshot_from='127.0.0.1',
            start_ts=None,
            abort_on_exit=True,
            dutils=skaled_am.dutils,
            passive_node=False,
            historic_state=False,
            part_of_node=skaled_am.schain.part_of_node,
        )
        assert monitor_skaled_container_mock.call_count == 1
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_skaled_container_snapshot_delay_start_action(skaled_am: SkaledActionManager):
    ts = int(time.time())
    try:
        skaled_am.volume()
        with mock.patch(
            'core.monitor.schain.action_skaled.monitor_skaled_container', new=mock.Mock()
        ) as monitor_skaled_container_mock:
            skaled_am.skaled_container(download_snapshot=True, start_ts=ts)

        monitor_skaled_container_mock.assert_called_with(
            skaled_am.schain.name,
            chain_record=skaled_am.chain_record,
            skaled_status=skaled_am.skaled_status,
            download_snapshot=True,
            snapshot_from='127.0.0.1',
            start_ts=ts,
            abort_on_exit=True,
            dutils=skaled_am.dutils,
            passive_node=False,
            historic_state=False,
            part_of_node=skaled_am.schain.part_of_node,
        )
        assert monitor_skaled_container_mock.call_count == 1
    finally:
        skaled_am.cleanup_schain_docker_entity()


def test_recreated_skaled_container_action_exit_reached(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    skaled_status_exit_time_reached: SkaledStatus,
):
    try:
        skaled_am.volume()
        with mock.patch(
            'core.monitor.schain.action_skaled.monitor_skaled_container',
            monitor_skaled_container_mock,
        ):
            assert not skaled_checks.skaled_container
            skaled_am.recreated_skaled_container()
            assert not skaled_checks.skaled_container
            skaled_am.recreated_skaled_container(abort_on_exit=False)
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
def ima_linked(econfig: ExternalConfig) -> None:
    state = econfig.get()
    state.ima_linked = True
    econfig.update(state)


def test_recreated_chain_containers(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    ima_linked: None,
    cleanup_ima: None,
    schain_db: SchainName,
    dutils: DockerUtils,
):
    name = schain_db

    skaled_am.volume()
    skaled_am.recreated_chain_containers()
    schain_container = f'sk_skaled_{name}'
    ima_container = f'sk_ima_{name}'
    dutils.wait_for_container_creation(schain_container)
    dutils.wait_for_container_creation(ima_container)
    skaled_created_ts = dutils.get_container_created_ts(schain_container)
    ima_created_ts = dutils.get_container_created_ts(ima_container)

    time.sleep(1)

    skaled_am.recreated_chain_containers()
    dutils.wait_for_container_creation(schain_container)
    dutils.wait_for_container_creation(ima_container)

    skaled_ts = dutils.get_container_created_ts(schain_container)
    ima_ts = dutils.get_container_created_ts(ima_container)
    assert skaled_ts > skaled_created_ts
    assert ima_ts > ima_created_ts


def test_ima_container_action_from_scratch(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    schain_config: dict,
    ima_linked,
    cleanup_ima,
    ima_migration_schedule,
    dutils: DockerUtils,
):
    skaled_am.ima_container()
    containers = dutils.get_all_ima_containers(all=True)
    assert len(containers) == 1
    container_name = containers[0].name
    assert container_name == f'sk_ima_{skaled_am.name}'
    image = dutils.get_container_image_name(container_name)
    assert image == 'alpine:3.22'


def test_ima_container_action_image_pulling(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    schain_config: dict,
    ima_linked,
    cleanup_ima,
    dutils: DockerUtils,
):
    dt = datetime.datetime.utcfromtimestamp(IMA_MIGRATION_TS - 5)
    with freezegun.freeze_time(dt):
        skaled_am.ima_container()
        containers = dutils.get_all_ima_containers(all=True)
        assert len(containers) == 1
        assert containers[0].name == f'sk_ima_{skaled_am.name}'
        container_name = containers[0].name
        assert container_name == f'sk_ima_{skaled_am.name}'
        image = dutils.get_container_image_name(container_name)
        assert image == 'alpine:3.23'
        assert dutils.pulled('alpine:3.23')


def test_ima_container_action_image_migration(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    schain_config: dict,
    ima_linked,
    cleanup_ima,
    dutils: DockerUtils,
):
    dt = datetime.datetime.utcfromtimestamp(IMA_MIGRATION_TS + 5)
    with freezegun.freeze_time(dt):
        skaled_am.ima_container()
        containers = dutils.get_all_ima_containers(all=True)
        assert len(containers) == 1
        container_name = containers[0].name
        assert container_name == f'sk_ima_{skaled_am.name}'
        image = dutils.get_container_image_name(container_name)
        assert image == 'alpine:3.22'


def test_ima_container_action_time_frame_migration(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    schain_config: dict,
    ima_linked,
    cleanup_ima,
    dutils: DockerUtils,
):
    dt = datetime.datetime.utcfromtimestamp(IMA_MIGRATION_TS - 5)
    with freezegun.freeze_time(dt):
        with mock.patch(
            'core.chain.containers.get_image_name',
            return_value='alpine:3.23',
        ):
            skaled_am.ima_container()
            containers = dutils.get_all_ima_containers(all=True)
            assert len(containers) == 1
            container_name = containers[0].name
            assert container_name == f'sk_ima_{skaled_am.name}'
            image = dutils.get_container_image_name(container_name)
            assert image == 'alpine:3.23'
            actual_time_frame = int(dutils.get_container_env_value(container_name, 'TIME_FRAMING'))
            assert actual_time_frame == 1800

    dt = datetime.datetime.utcfromtimestamp(IMA_MIGRATION_TS + 5)
    with freezegun.freeze_time(dt):
        with mock.patch(
            'core.chain.containers.get_image_name',
            return_value='alpine:3.23',
        ):
            skaled_am.ima_container()
            containers = dutils.get_all_ima_containers(all=True)
            assert len(containers) == 1
            container_name = containers[0].name
            assert container_name == f'sk_ima_{skaled_am.name}'
            image = dutils.get_container_image_name(container_name)
            assert image == 'alpine:3.23'
            actual_time_frame = int(dutils.get_container_env_value(container_name, 'TIME_FRAMING'))
            assert actual_time_frame == 900


@pytest.mark.skip(reason="test needs new version of ima container that doesn't require ABIs")
def test_ima_container_action_not_linked(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    schain_db: SchainName,
    _schain_name: SchainName,
    cleanup_ima_containers,
    ima_migration_schedule,
    dutils: DockerUtils,
):
    skaled_am.ima_container()
    assert skaled_checks.ima_container


def test_cleanup_empty_action(skaled_am: SkaledActionManager, skaled_checks: SkaledChecks):
    skaled_am.cleanup_schain_docker_entity()
    assert not skaled_checks.skaled_container


def test_display_skaled_logs(skaled_am: SkaledActionManager, _schain_name: SchainName):
    skaled_am.log_executed_blocks()
    # Don't display if no container
    skaled_am.display_skaled_logs()
    try:
        skaled_am.volume()
        with mock.patch(
            'core.monitor.schain.action_skaled.monitor_skaled_container',
            monitor_skaled_container_mock,
        ):
            skaled_am.skaled_container()
    finally:
        skaled_am.display_skaled_logs()
        skaled_am.cleanup_schain_docker_entity()


@freezegun.freeze_time(CURRENT_DATETIME)
def test_upd_chain_record(skaled_am: SkaledActionManager, skaled_checks: SkaledChecks):
    # Prepare fake record
    r = SChainRecord.get_by_name(skaled_am.name)
    r.set_restart_count(1)
    r.set_failed_rpc_count(1)

    assert r.monitor_last_seen != CURRENT_DATETIME
    skaled_am._upd_last_seen()
    r = SChainRecord.get_by_name(skaled_am.name)
    assert r.monitor_last_seen == CURRENT_DATETIME
    skaled_am._upd_chain_record()
    r = SChainRecord.get_by_name(skaled_am.name)

    assert not r.first_run
    assert r.restart_count == 0
    assert r.failed_rpc_count == 0


def test_update_config(skaled_am: SkaledActionManager, skaled_checks: SkaledChecks):
    folder = schain_config_dir(skaled_am.name)
    config_path = os.path.join(folder, f'schain_{skaled_am.name}.json')
    os.remove(config_path)
    assert not skaled_checks.config

    assert not skaled_checks.config_updated
    upstream_path = UpstreamConfigFilename(
        skaled_am.name, rotation_id=5, ts=int(time.time())
    ).abspath(folder)

    config_content = {'config': 'mock_v5'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)
    skaled_am.update_config()
    with open(config_path) as config_file:
        assert json.load(config_file) == config_content
    assert skaled_checks.config
    assert skaled_checks.config_updated

    time.sleep(1)
    upstream_path = UpstreamConfigFilename(
        skaled_am.name, rotation_id=6, ts=int(time.time())
    ).abspath(folder)

    config_content = {'config': 'mock_v6'}
    with open(upstream_path, 'w') as upstream_file:
        json.dump(config_content, upstream_file)

    assert skaled_checks.config
    assert not skaled_checks.config_updated
    skaled_am.update_config()

    assert skaled_checks.config_updated


def test_firewall_rules_action(
    skaled_am: SkaledActionManager,
    skaled_checks: SkaledChecks,
    rule_controller: IRuleController,
    econfig: ExternalConfig,
):
    assert not skaled_checks.firewall_rules
    skaled_am.firewall_rules()
    assert skaled_checks.firewall_rules
    added_rules = list(rule_controller.firewall_manager.rules)
    assert added_rules == [
        SChainRule(
            first_port=10000,
            last_port=10063,
            interface_exception=LOOPBACK_INTERFACE,
            action=Action.DROP,
        ),
        SChainRule(first_port=10000, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(first_port=10001, first_ip='1.1.1.1', last_ip='2.2.2.2'),
        SChainRule(first_port=10001, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10002),
        SChainRule(first_port=10003),
        SChainRule(first_port=10004, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(first_port=10005, first_ip='1.1.1.1', last_ip='2.2.2.2'),
        SChainRule(first_port=10005, first_ip='127.0.0.2', last_ip='127.0.0.2'),
        SChainRule(first_port=10005, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10007),
        SChainRule(first_port=10008),
        SChainRule(first_port=10009),
        SChainRule(first_port=10010, first_ip='127.0.0.2', last_ip='127.0.0.2'),
    ]
