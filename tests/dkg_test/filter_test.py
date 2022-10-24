import mock
import pytest

from core.schains.dkg.broadcast_filter import Filter

SCHAIN_NAME = 'test'
N = 16


@pytest.fixture
def filter_mock(skale):
    filter = Filter(skale, SCHAIN_NAME, N)
    filter.first_unseen_block = skale.web3.eth.getBlock("latest")['number'] - 100
    return filter


def test_get_events(skale, filter_mock):
    def assert_not_called_with(self, *args, **kwargs):
        try:
            self.assert_called_with(*args, **kwargs)
        except AssertionError:
            return
        raise AssertionError()

    mock.Mock.assert_not_called_with = assert_not_called_with
    first = filter_mock.first_unseen_block
    latest = skale.web3.eth.getBlock("latest")['number']
    with mock.patch.object(skale.web3.eth, 'getBlock',
                           wraps=skale.web3.eth.getBlock) as block_mock:
        result = filter_mock.get_events()
        block_mock.assert_not_called_with(first - 1)
        block_mock.assert_any_call(first, full_transactions=True)
        block_mock.assert_any_call(latest, full_transactions=True)
        assert filter_mock.first_unseen_block > latest
        assert isinstance(result, list)


def test_get_events_from_start(skale, filter_mock):
    latest = skale.web3.eth.getBlock("latest")['number']
    mock_start_block = skale.web3.eth.getBlock("latest")['number'] - 100
    with mock.patch.object(skale.web3.eth, 'getBlock',
                           wraps=skale.web3.eth.getBlock) as block_mock, \
            mock.patch.object(skale.dkg.contract.functions.getChannelStartedBlock, 'call',
                              new=mock.Mock(return_value=mock_start_block)):
        result = filter_mock.get_events(from_channel_started_block=True)
        block_mock.assert_any_call(mock_start_block, full_transactions=True)
        block_mock.assert_any_call(latest, full_transactions=True)
        assert filter_mock.first_unseen_block > latest
        assert isinstance(result, list)
