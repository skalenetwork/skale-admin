from datetime import datetime
from unittest import mock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from core.checks.fair import SkaledChecks
from core.config.schain.static_params import get_fair_chain_name
from core.monitor.fair.action_skaled import FairSkaledActionManager
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from tests.utils import TEST_TASK_SLEEP
from tools.helper import is_passive
from tools.settings import BaseAdminSettings


@pytest.fixture
def chain_name(st: BaseAdminSettings):
    return get_fair_chain_name(st.env_type)


@pytest.fixture
def chain_record(chain_name):
    return ChainRecord(name=chain_name)


@pytest.fixture
def scheduler():
    sch = BackgroundScheduler()
    sch.start()
    yield sch
    sch.shutdown()


@pytest.fixture
def node_config_fair():
    node_config = NodeConfig()
    node_config.id = 1
    return node_config


@pytest.fixture
def skaled_checks(chain_name, chain_record, rule_controller, dutils):
    return SkaledChecks(
        chain_name=chain_name,
        chain_record=chain_record,
        rule_controller=rule_controller,
        dutils=dutils,
        passive_node=is_passive(),
    )


@pytest.fixture
def skaled_am(
    chain_name,
    node_config_fair,
    rule_controller,
    dutils,
    skaled_checks,
    scheduler,
) -> FairSkaledActionManager:
    return FairSkaledActionManager(
        chain_name=chain_name,
        rule_controller=rule_controller,
        checks=skaled_checks,
        node_config=node_config_fair,
        scheduler=scheduler,
        dutils=dutils,
        post_run_delay=TEST_TASK_SLEEP,
        schain_cleanup_timeout=TEST_TASK_SLEEP,
    )


def test_fair_skaled_action_manager_init(
    skaled_am,
):
    assert isinstance(skaled_am, FairSkaledActionManager)
    assert isinstance(skaled_am.checks, skaled_am.checks.__class__)
    assert isinstance(skaled_am.rule_controller, skaled_am.rule_controller.__class__)
    assert isinstance(skaled_am.scheduler, BackgroundScheduler)


def test_fair_skaled_action_manager_scheduler(
    skaled_am: FairSkaledActionManager,
):
    restart_deadline = int(datetime.now().timestamp()) + 3600
    assert skaled_am.schedule_skaled_restart(restart_deadline=restart_deadline)
    assert not skaled_am.schedule_skaled_restart(restart_deadline=restart_deadline)


def test_fair_skaled_action_manager_recreated_skaled_container(
    skaled_am: FairSkaledActionManager,
):
    skaled_am.chain_record.set_restart_ts(int(datetime.now().timestamp()))
    assert skaled_am.chain_record.restart_ts
    assert skaled_am.chain_record.restart_ts > 0
    with mock.patch(
        'core.monitor.fair.action_skaled.monitor_skaled_container'
    ) as monitor_skaled_container_mock:
        assert skaled_am.recreated_skaled_container()
        monitor_skaled_container_mock.assert_called()
    assert skaled_am.chain_record.restart_ts == 0
