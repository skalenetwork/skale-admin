from datetime import datetime

import freezegun
import mock
import pytest
from redis import BlockingConnectionPool, Redis

from tools.notifications.messages import (cleanup_notification_state,
                                          compose_balance_message,
                                          compose_checks_message,
                                          notify_checks, notify_balance,
                                          notify_repair_mode,
                                          send_message)

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


client = Redis(connection_pool=BlockingConnectionPool())


NODE_INFO = {'node_id': 1, 'node_ip': '1.1.1.1'}


@mock.patch('tools.notifications.messages.send_message_to_telegram')
@freezegun.freeze_time(CURRENT_DATETIME)
def test_send_message(task_mock):
    message = ['key1: value1', 'key2: value2']
    send_message(message)
    expected_call = ('key1: value1\nkey2: value2\n\nTimestamp: 1594903080\n'
                     'Datetime: Thu Jul 16 12:38:00 2020')
    called_with = task_mock.delay.call_args[0][2]
    assert called_with == expected_call


def test_compose_checks_message_raw():
    checks = {
        'dkg': False,
        'config': True,
        'data_dir': True,
        'volume': True,
        'container': False,
        'firewall_rules': True,
        'rpc': False
    }
    schain_name = 'test-schain'
    result = compose_checks_message(schain_name, NODE_INFO, checks, raw=True)
    expected = {
        'schain_name': 'test-schain', 'node_id': 1,
        'node_ip': '1.1.1.1',
        'checks': {
            'dkg': False, 'config': True,
            'data_dir': True, 'volume': True, 'container': False,
            'firewall_rules': True, 'rpc': False
        }
    }
    assert result == expected


def test_compose_checks_message_success():
    checks = {
        'dkg': True,
        'config': True,
        'data_dir': True,
        'volume': True,
        'container': True,
        'firewall_rules': True,
        'rpc': True,
        'blocks': True,
        'ima': True
    }
    schain_name = 'test-schain'
    result = compose_checks_message(schain_name, NODE_INFO, checks)
    expected = [
        'Node ID: 1, IP: 1.1.1.1',
        'sChain name: test-schain',
        '\n\u2705 All checks passed'
    ]
    assert result == expected


def test_compose_checks_message_fail():
    checks = {
        'dkg': True,
        'config': True,
        'data_dir': True,
        'volume': True,
        'container': False,
        'firewall_rules': True,
        'rpc': False,
        'blocks': False,
        'ima': False
    }
    schain_name = 'test-schain'
    result = compose_checks_message(schain_name, NODE_INFO, checks)
    expected = [
        'Node ID: 1, IP: 1.1.1.1',
        'sChain name: test-schain',
        '\n\u2757 Some checks failed\n',
        '\u274C container',
        '\u274C rpc',
        '\u274C blocks',
        '\u274C ima'
    ]
    assert result == expected


def test_compose_balance_message():
    balance, required_balance = 1, 2
    result = compose_balance_message(NODE_INFO, balance, required_balance)
    assert result == ['\u2757 Balance on node is too low \n', 'Node ID: 1, IP: 1.1.1.1',
                      'Balance: 1 ETH', 'Required: 2 ETH']


def test_compose_balance_message_success():
    balance, required_balance = 1, 0.5
    result = compose_balance_message(NODE_INFO, balance, required_balance)
    assert result == ['\u2705 Node id: has enough balance \n', 'Node ID: 1, IP: 1.1.1.1',
                      'Balance: 1 ETH', 'Required: 0.5 ETH']


@pytest.fixture
def cleaned_state():
    cleanup_notification_state()


def test_cleanup_empty_notification_state():
    redis_client_mock = mock.Mock()
    redis_client_mock.keys = mock.Mock(return_value=[])
    cleanup_notification_state(client=redis_client_mock)
    redis_client_mock.delete.assert_not_called()


@mock.patch('tools.notifications.messages.send_message')
def test_notify_balance(send_message_mock, cleaned_state):
    def get_state_data():
        count_key = 'messages.balance.count'
        state_key = 'messages.balance.state'
        return int(client.get(count_key) or 0), int(client.get(state_key) or -1)

    count, state = get_state_data()
    assert count == 0 and state == -1

    # enough balance. Only one attempt allowed
    balance, required_balance = 1, 0.5

    notify_balance(NODE_INFO, balance, required_balance)
    assert send_message_mock.call_count == 1

    count, state = get_state_data()
    assert count == 1 and state == 1

    notify_balance(NODE_INFO, balance, required_balance)
    assert send_message_mock.call_count == 1

    count, state = get_state_data()
    assert count == 2 and state == 1

    # not enough balance
    balance, required_balance = 1, 2

    initial_call_count = send_message_mock.call_count
    notify_balance(NODE_INFO, balance, required_balance)
    assert send_message_mock.call_count == initial_call_count + 1
    count, state = get_state_data()
    assert count == 1 and state == 0

    # Next is not allowed
    notify_balance(NODE_INFO, balance, required_balance)
    assert send_message_mock.call_count == initial_call_count + 1
    count, state = get_state_data()
    assert count == 2 and state == 0


@mock.patch('tools.notifications.messages.send_message')
def test_notify_checks(send_message_mock, cleaned_state):
    schain_name = 'test-schain'

    def get_state_data():
        count_key = f'messages.checks.{schain_name}.count'
        state_key = f'messages.checks.{schain_name}.state'
        count = int(client.get(count_key) or 0)
        saved_state_bytes = client.get(state_key) or b''
        saved_state = saved_state_bytes.decode('utf-8')
        return count, saved_state

    def check_state(expected_count, expected_state):
        count, state = get_state_data()
        assert count == expected_count and state == expected_state

    successfull_checks = {
        'dkg': True,
        'config': True,
        'data_dir': True,
        'volume': True,
        'container': True,
        'firewall_rules': True,
        'rpc': True
    }
    failed_checks_1 = {
        'dkg': False,
        'config': True,
        'data_dir': True,
        'volume': True,
        'container': False,
        'firewall_rules': True,
        'rpc': False
    }
    failed_checks_2 = {
        'dkg': False,
        'config': True,
        'data_dir': True,
        'volume': False,
        'container': False,
        'firewall_rules': False,
        'rpc': False
    }

    check_state(0, '')

    # Successful checks
    notify_checks(schain_name, NODE_INFO, successfull_checks)
    assert send_message_mock.call_count == 1

    check_state(1, "[('config', True), ('container', True), ('data_dir', True), ('dkg', True), ('firewall_rules', True), ('rpc', True), ('volume', True)]")  # noqa

    notify_checks(schain_name, NODE_INFO, successfull_checks)
    assert send_message_mock.call_count == 1

    count, state = get_state_data()
    check_state(2, "[('config', True), ('container', True), ('data_dir', True), ('dkg', True), ('firewall_rules', True), ('rpc', True), ('volume', True)]")  # noqa

    # Failed checks
    initial_call_count = send_message_mock.call_count
    notify_checks(schain_name, NODE_INFO, failed_checks_1)
    assert send_message_mock.call_count == initial_call_count + 1
    check_state(1, "[('config', True), ('container', False), ('data_dir', True), ('dkg', False), ('firewall_rules', True), ('rpc', False), ('volume', True)]")  # noqa

    # Next is not allowed
    notify_checks(schain_name, NODE_INFO, failed_checks_1)
    assert send_message_mock.call_count == initial_call_count + 1
    check_state(2, "[('config', True), ('container', False), ('data_dir', True), ('dkg', False), ('firewall_rules', True), ('rpc', False), ('volume', True)]")  # noqa

    # If state changed message should be sent
    notify_checks(schain_name, NODE_INFO, failed_checks_2)
    assert send_message_mock.call_count == initial_call_count + 2
    check_state(1, "[('config', True), ('container', False), ('data_dir', True), ('dkg', False), ('firewall_rules', False), ('rpc', False), ('volume', False)]")  # noqa


@mock.patch('tools.notifications.messages.send_message')
def test_notify_repair(send_message_mock):
    notify_repair_mode(NODE_INFO, 'test-schain')
    send_message_mock.assert_called_with(
        ['\u2757 Repair mode for test-schain enabled \n',
         'Node ID: 1', 'Node IP: 1.1.1.1', 'SChain: test-schain']
    )
