from core.schains.runner import set_rotation_for_schain, check_container_exit
from tests.schains.creator_test import SCHAIN
import mock
import json


class ResponseMock:
    def json(self):
        return {}


def test_set_rotation():
    with mock.patch('core.schains.helper.requests.post',
                    new=mock.Mock(return_value=ResponseMock())) as post:
        set_rotation_for_schain(SCHAIN, 100)
        args, kwargs = post.call_args
        data = json.loads(kwargs['data'])
        params = {
            'finishTime': 100
        }
        assert kwargs['url'] == 'http://127.0.0.1:2234'
        assert data['method'] == 'setSchainExitTime'
        assert data['params'] == params


def test_check_container_exit():
    info_mock = {
        'status': 'exited',
        'stats': {
            'State': {
                'ExitCode': 1
            }
        }
    }
    with mock.patch('core.schains.runner.DockerUtils.get_info',
                    new=mock.Mock(return_value=info_mock)):
        assert check_container_exit(SCHAIN['name'])

    with mock.patch('core.schains.runner.DockerUtils.get_info',
                    new=mock.Mock(return_value=info_mock)):
        assert not check_container_exit(SCHAIN['name'], zero_exit_code=True)

    info_mock['stats']['State']['ExitCode'] = 0

    with mock.patch('core.schains.runner.DockerUtils.get_info',
                    new=mock.Mock(return_value=info_mock)):
        assert check_container_exit(SCHAIN['name'], zero_exit_code=True)
