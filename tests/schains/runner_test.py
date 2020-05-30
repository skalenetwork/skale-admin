from core.schains.runner import set_rotation_for_schain
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
            'finishTime': 100,
            'isExit': False
        }
        assert kwargs['url'] == 'http://127.0.0.1:2234'
        assert data['method'] == 'setRestartOrExitTime'
        assert data['params'] == params
