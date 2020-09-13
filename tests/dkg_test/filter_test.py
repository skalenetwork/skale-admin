import mock
import pytest

from tools.bls.skale_dkg_broadcast_filter import Filter

SCHAIN_NAME = 'test'
N = 16


@pytest.fixture
def filter_mock(skale):
    filter = Filter(skale, SCHAIN_NAME, N)
    filter.last_viewed_block = skale.web3.eth.getBlock("latest")['number'] // 2
    return filter


def test_get_events(skale, filter_mock):
    def assert_not_called_with(self, *args, **kwargs):
        try:
            self.assert_called_with(*args, **kwargs)
        except AssertionError:
            return
        raise AssertionError()

    mock.Mock.assert_not_called_with = assert_not_called_with
    first = filter_mock.last_viewed_block
    latest = skale.web3.eth.getBlock("latest")['number']
    with mock.patch.object(skale.web3.eth, 'getBlock',
                           wraps=skale.web3.eth.getBlock) as block_mock:
        result = filter_mock.get_events()
        block_mock.assert_not_called_with(first - 1)
        block_mock.assert_any_call(first)
        block_mock.assert_any_call(latest)
        assert isinstance(result, list)


def test_get_events_from_start(skale, filter_mock):
    latest = skale.web3.eth.getBlock("latest")['number']
    with mock.patch.object(skale.web3.eth, 'getBlock',
                           wraps=skale.web3.eth.getBlock) as block_mock, \
            mock.patch.object(skale.dkg.contract.functions.getChannelStartedBlock, 'call',
                              new=mock.Mock(return_value=0)):
        result = filter_mock.get_events(from_channel_started_block=True)
        block_mock.assert_any_call(0)
        block_mock.assert_any_call(latest)
        assert isinstance(result, list)
