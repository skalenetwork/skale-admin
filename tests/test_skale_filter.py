import pytest
import mock
from tools.helper import SkaleFilter, SkaleFilterError

from skale.utils.contracts_provision.utils import (
    generate_random_node_data, generate_random_schain_data
)


def test_skale_filter(skale):
    sfilter = SkaleFilter(
        skale.dkg.contract.events.BroadcastAndKeyShare,
        from_block=0,
        argument_filters={}
    )
    assert isinstance(sfilter.get_events(), list)


def test_remove_schain_filter(skale):
    for _ in range(0, 1):
        ip, _, port, name = generate_random_node_data()
        skale.manager.create_node(ip, port, name, wait_for=True)

    sfilter = SkaleFilter(
        skale.schains.contract.events.SchainCreated,
        from_block=0,
        argument_filters={}
    )
    type_of_nodes, lifetime_seconds, name = generate_random_schain_data()
    price_in_wei = skale.schains.get_schain_price(type_of_nodes,
                                                  lifetime_seconds)
    tx_res = skale.manager.create_schain(lifetime_seconds, type_of_nodes,
                                         price_in_wei, name, wait_for=True)
    assert tx_res.receipt['status'] == 1

    events = sfilter.get_events()
    assert events[-1]['args']['name'] == name


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
