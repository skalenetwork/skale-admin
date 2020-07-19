from datetime import datetime

import freezegun
import mock

from tools.notifications.messages import compose_failed_checks_message, send_message

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


@mock.patch('tools.notifications.messages.send_message_to_telegram')
@freezegun.freeze_time(CURRENT_DATETIME)
def test_send_message(task_mock):
    message = {'data': 'test'}
    send_message(message)
    expected = {
        'data': 'test',
        'timestamp': CURRENT_TIMESTAMP,
        'datetime': CURRENT_DATETIME
    }
    called_with = task_mock.delay.call_args[0][2]
    assert called_with == expected


def test_compose_failed_checks_message():
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
    node_id = 1
    result = compose_failed_checks_message(schain_name, node_id, checks)
    expected = '❗ Checks failed \n\nNode ID: 1\nsChain name: test-schain\nData directory: ✅\nDKG: ❌\nConfig: ✅\nVolume: ✅\nContainer: ❌\nFirewall: ✅\nRPC: ❌\n'  # noqa
    assert result == expected
