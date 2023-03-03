import mock
import json

from core.schains.process_manager import get_leaving_schains_for_node
from core.schains.runner import is_exited
from core.schains.rotation import set_rotation_for_schain


class ResponseMock:
    def json(self):
        return {}


def test_set_rotation(schain_config):
    with mock.patch('core.schains.rotation.requests.post',
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


def test_is_exited(dutils):
    schain_name = 'schain_test'
    info_mock = {
        'status': 'exited',
        'stats': {
            'State': {
                'ExitCode': 1
            }
        }
    }
    get_info = dutils.get_info
    try:
        dutils.get_info = mock.Mock(return_value=info_mock)
        assert is_exited(schain_name, dutils=dutils)
    finally:
        dutils.get_info = get_info


def test_get_leaving_schains_for_node(skale, node_config):  # TODO: improve test
    leaving_schains = get_leaving_schains_for_node(skale, node_config.id)
    assert isinstance(leaving_schains, list)
