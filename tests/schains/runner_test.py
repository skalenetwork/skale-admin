from core.schains.runner import set_rotation_for_schain, is_exited, is_exited_with_zero
import mock
import json


class ResponseMock:
    def json(self):
        return {}


def test_set_rotation(schain_config):
    with mock.patch('core.schains.helper.requests.post',
                    new=mock.Mock(return_value=ResponseMock())) as post:
        schain_name = schain_config['skaleConfig']['sChain']['schainName']
        set_rotation_for_schain(schain_name, 100)
        args, kwargs = post.call_args
        data = json.loads(kwargs['data'])
        params = {
            'finishTime': 100
        }
        assert kwargs['url'] == 'http://127.0.0.1:10003'
        assert data['method'] == 'setSchainExitTime'
        assert data['params'] == params


def test_is_exited():
    schain_name = 'schain_test'
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
        assert is_exited(schain_name)


def test_is_exited_with_zero():
    schain_name = 'schain_test'
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
        assert not is_exited_with_zero(schain_name)

    info_mock['stats']['State']['ExitCode'] = 0

    with mock.patch('core.schains.runner.DockerUtils.get_info',
                    new=mock.Mock(return_value=info_mock)):
        assert is_exited_with_zero(schain_name)
