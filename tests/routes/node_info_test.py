import freezegun
import mock
import pkg_resources
import pytest
from datetime import datetime
from flask import Flask

from tests.utils import get_bp_data, post_bp_data
from tools.configs.flask import SKALE_LIB_NAME
from tools.configs.tg import TG_API_KEY, TG_CHAT_ID
from tools.configs.web3 import ENDPOINT
from tools.docker_utils import DockerUtils
from web.routes.node_info import construct_node_info_bp

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_node_info_bp(skale, dutils))
    return app.test_client()


def test_rpc_healthcheck(skale_bp):
    data = get_bp_data(skale_bp, '/get-rpc-credentials')
    expected = {
        'status': 'ok',
        'payload': {
            'endpoint': ENDPOINT
        }
    }
    assert data == expected


def test_containers_healthcheck(skale_bp):
    data = get_bp_data(skale_bp, '/healthchecks/containers')
    dutils = DockerUtils(volume_driver='local')
    expected = {
        'status': 'ok',
        'payload': dutils.get_all_skale_containers(all=all, format=True)
    }
    assert data == expected


@freezegun.freeze_time(CURRENT_DATETIME)
def test_send_tg_notification(skale_bp):
    with mock.patch(
        'tools.notifications.messages.send_message_to_telegram',
        mock.Mock(return_value={'message': 'test'})
    ) as send_message_to_telegram_mock:
        data = post_bp_data(skale_bp, '/send-tg-notification',
                            {'message': ['test']})
        send_message_to_telegram_mock.delay.assert_called_once_with(
            TG_API_KEY,
            TG_CHAT_ID,
            'test\nTimestamp: 1594903080\n'
            'Datetime: Thu Jul 16 12:38:00 2020'
        )

    expected = {'status': 'ok',
                'payload': 'Message was sent successfully'}
    assert data == expected


def test_about(skale_bp, skale):
    expected = {
        'status': 'ok',
        'payload': {
            'libraries': {
                'javascript': 'N/A',  # get_js_package_version(),
                'skale.py': pkg_resources.get_distribution(SKALE_LIB_NAME).version
            },
            'contracts': {
                'token': skale.token.address,
                'manager': skale.manager.address,
            },
            'network': {
                'endpoint': ENDPOINT
            }
        }
    }
    data = get_bp_data(skale_bp, '/about-node')
    assert data == expected
