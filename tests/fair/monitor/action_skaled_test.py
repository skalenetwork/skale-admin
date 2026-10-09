from datetime import datetime
from unittest import mock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from skale_core.settings import BaseNodeSettings

from core.checks.fair import SkaledChecks, get_network_scope_ips_from_firewall
from core.config.schain.static_params import get_fair_chain_name
from core.firewall import Action, SChainRule
from core.monitor.fair.action_skaled import FairSkaledActionManager
from core.monitor.fair.monitor_skaled import (
    ProxySwitchSkaledMonitor,
    RegularSkaledMonitor,
    get_skaled_monitor,
)
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.redis.node_config_fair import NodeConfigFair
from core.utils.fair import get_local_skaled_endpoint_fair, update_local_skaled_endpoint
from tests.utils import TEST_TASK_SLEEP
from tools.constants.fair import SKALED_RESTART_JOB_NAME
from tools.helper import is_passive


@pytest.fixture
def chain_name(st: BaseNodeSettings):
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


def test_get_skaled_monitor_rpc_proxy_switch(skaled_am: FairSkaledActionManager, chain_record):
    chain_record.set_rpc_proxy_mode(False)
    chain_record.set_restart_ts(0)
    status = {'config': True, 'volume': True, 'config_updated': True, 'skaled_container': True}
    mon = get_skaled_monitor(skaled_am, status, chain_record, None)
    assert mon == RegularSkaledMonitor
    with mock.patch('core.nginx.mode.is_rpc_proxy_enabled', return_value=True):
        with mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=False):
            mon = get_skaled_monitor(skaled_am, status, chain_record, None)
            assert mon == RegularSkaledMonitor
        with mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=True):
            mon = get_skaled_monitor(skaled_am, status, chain_record, None)
            assert mon == ProxySwitchSkaledMonitor


def test_proxy_switch_monitor_schedules_restart(skaled_am: FairSkaledActionManager):
    with (
        mock.patch.object(RegularSkaledMonitor, 'execute'),
        mock.patch(
            'core.monitor.fair.action_skaled.random_timestamp_between',
            side_effect=lambda start, end: end,
        ),
    ):
        ProxySwitchSkaledMonitor(skaled_am).execute()
    job = skaled_am.scheduler.get_job(SKALED_RESTART_JOB_NAME)
    assert job is not None
    # the latest restart lands an hour out, so the committee spreads over that window
    assert 3595 <= skaled_am.chain_record.restart_ts - int(datetime.now().timestamp()) <= 3600


def test_proxy_peers(skaled_checks: SkaledChecks):
    config = {
        'skaleConfig': {
            'sChain': {
                'nodes': {
                    '1': {'group': [{'ip': '10.2.0.1'}]},
                    '2': {'group': [{'ip': '10.2.0.2'}, {'ip': '10.1.0.1'}]},
                }
            }
        }
    }
    rules = [
        SChainRule(first_port=10001, first_ip='10.1.0.1'),
        SChainRule(first_port=10001, first_ip='10.1.0.4'),
        SChainRule(first_port=10003),
        SChainRule(first_port=10001, first_ip='10.1.0.3', action=Action.DROP),
    ]
    with mock.patch('core.checks.fair.NFTablesController') as nft:
        nft.return_value.rules = rules
        assert get_network_scope_ips_from_firewall() == ['10.1.0.1', '10.1.0.4']
        # the committee that took over at timestamp 2 and the network the firewall accepts
        assert sorted(skaled_checks.proxy_peers(config)) == [
            '10.1.0.1/32',
            '10.1.0.4/32',
            '10.2.0.2/32',
        ]


def test_local_endpoint_follows_rpc_proxy_mode(chain_record):
    config = {'skaleConfig': {'nodeInfo': {'httpRpcPort': 1234, 'wsRpcPort': 1233}}}
    with mock.patch('core.utils.fair.ConfigFileManager') as cfm:
        cfm.return_value.skaled_config = config
        chain_record.set_rpc_proxy_mode(False)
        assert get_local_skaled_endpoint_fair() == 'http://127.0.0.1:1234'
        chain_record.set_rpc_proxy_mode(True)
        update_local_skaled_endpoint()
    # transaction-manager reads it from there
    assert NodeConfigFair().local_endpoint == 'http://127.0.0.1:1266'
    chain_record.set_rpc_proxy_mode(False)
