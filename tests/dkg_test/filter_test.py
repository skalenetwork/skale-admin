import mock
import pytest

from tools.bls.skale_dkg_broadcast_filter import Filter

SCHAIN_NAME = 'test'
N = 16


@pytest.fixture
def filter_mock(skale):
    filter = Filter(skale, SCHAIN_NAME, N)
    filter.last_viewed_block = 1
    return filter


def test_get_events(skale, filter_mock):
    latest = skale.web3.eth.getBlock("latest")['number']
    with mock.patch.object(skale.web3.eth, 'getBlock',
                           wraps=skale.web3.eth.getBlock) as block_mock:
        filter_mock.get_events()
        block_mock.assert_any_call(1)
        block_mock.assert_any_call(latest)
