import pytest
import mock
from tools.helper import SkaleFilter, SkaleFilterError


def test_skale_filter(skale):
    sfilter = SkaleFilter(
        skale.dkg.contract.events.BroadcastAndKeyShare,
        from_block=0,
        argument_filters={}
    )
    assert isinstance(sfilter.get_events(), list)


def test_skale_filter_with_events(skale):
    events = [{'event_id': 1}, {'event_id': 2}]

    def create_filter_mock(*, fromBlock=0, toBlock=0, argument_filters={}):
        cf_mock = mock.Mock()
        cf_mock.get_all_entries = mock.Mock(
            return_value=events
        )
        return cf_mock

    with mock.patch.object(
        skale.dkg.contract.events.BroadcastAndKeyShare, 'createFilter',
        new=create_filter_mock
    ):
        sfilter = SkaleFilter(
            skale.dkg.contract.events.BroadcastAndKeyShare,
            from_block=0,
            argument_filters={}
        )
        assert sfilter.get_events() == events


def test_skale_filter_with_exception(skale):
    events = [{'event_id': 1}, {'event_id': 2}]

    def create_filter_mock(*, fromBlock=0, toBlock=0, argument_filters={}):
        cf_mock = mock.Mock()
        cf_mock.get_all_entries = mock.Mock(
            side_effect=ValueError('filter not found'),
            return_value=events
        )
        return cf_mock

    with mock.patch.object(
        skale.dkg.contract.events.BroadcastAndKeyShare, 'createFilter',
        new=create_filter_mock
    ):
        sfilter = SkaleFilter(
            skale.dkg.contract.events.BroadcastAndKeyShare,
            from_block=0,
            argument_filters={},
            retries=2
        )

        with pytest.raises(SkaleFilterError):
            sfilter.get_events()
