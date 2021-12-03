import pytest

from core.schains.firewall.rule_controller import IpRange, NotInitializedError
from core.schains.firewall.types import SChainRule, SkaledPorts

from tests.utils import SChainTestRuleController


def test_schain_rule_controller():
    own_ip = '3.3.3.3'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10064
    sync_ip_ranges = [
        IpRange(start_ip='10.10.10.10', end_ip='15.15.15.15'),
        IpRange(start_ip='15.15.15.15', end_ip='18.18.18.18')
    ]

    expected_rules = {
        SChainRule(port=10064, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10064, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10064, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10065, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10065, first_ip='10.10.10.10', last_ip='15.15.15.15'),
        SChainRule(port=10065, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(port=10065, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10065, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10066, first_ip=None, last_ip=None),
        SChainRule(port=10067, first_ip=None, last_ip=None),
        SChainRule(port=10068, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10068, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10068, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10069, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10069, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10069, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10071, first_ip=None, last_ip=None),
        SChainRule(port=10072, first_ip=None, last_ip=None),
        SChainRule(port=10073, first_ip=None, last_ip=None),
        SChainRule(port=10074, first_ip=None, last_ip=None),
        SChainRule(port=10075, first_ip=None, last_ip=None),
        SChainRule(port=10076, first_ip=None, last_ip=None),
        SChainRule(port=10077, first_ip=None, last_ip=None)
    }
    src = SChainTestRuleController(
        'test',
        base_port,
        own_ip,
        node_ips,
        SkaledPorts,
        sync_ip_ranges=sync_ip_ranges
    )
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    new_sync_ip_ranges = [
        IpRange(start_ip='15.15.15.15', end_ip='18.18.18.18'),
        IpRange(start_ip='20.20.20.20', end_ip='21.21.21.21')
    ]
    new_node_ips = ['1.1.1.1', '5.5.5.5', '3.3.3.3', '4.4.4.4']
    src.sync_ip_ranges = new_sync_ip_ranges
    src.node_ips = new_node_ips
    assert not src.is_rules_synced()
    src.sync()

    expected_rules = {
        SChainRule(port=10064, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10064, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10064, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10065, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10065, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(port=10065, first_ip='20.20.20.20', last_ip='21.21.21.21'),
        SChainRule(port=10065, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10065, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10066, first_ip=None, last_ip=None),
        SChainRule(port=10067, first_ip=None, last_ip=None),
        SChainRule(port=10068, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10068, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10068, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10069, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10069, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10069, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10071, first_ip=None, last_ip=None),
        SChainRule(port=10072, first_ip=None, last_ip=None),
        SChainRule(port=10073, first_ip=None, last_ip=None),
        SChainRule(port=10074, first_ip=None, last_ip=None),
        SChainRule(port=10075, first_ip=None, last_ip=None),
        SChainRule(port=10076, first_ip=None, last_ip=None),
        SChainRule(port=10077, first_ip=None, last_ip=None)
    }
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []


def test_schain_rule_controller_no_sync_rules():
    own_ip = '1.1.1.1'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10000
    expected_rules = {
        SChainRule(port=10000, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10000, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10001, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10001, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10002, first_ip=None, last_ip=None),
        SChainRule(port=10003, first_ip=None, last_ip=None),
        SChainRule(port=10004, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10004, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10005, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10005, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10007, first_ip=None, last_ip=None),
        SChainRule(port=10008, first_ip=None, last_ip=None),
        SChainRule(port=10009, first_ip=None, last_ip=None),
        SChainRule(port=10010, first_ip=None, last_ip=None),
        SChainRule(port=10011, first_ip=None, last_ip=None),
        SChainRule(port=10012, first_ip=None, last_ip=None),
        SChainRule(port=10013, first_ip=None, last_ip=None)
    }
    src = SChainTestRuleController(
        'test',
        base_port,
        own_ip,
        node_ips
    )
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []


def test_schain_rule_controller_configure():
    src = SChainTestRuleController('test')

    with pytest.raises(NotInitializedError):
        src.public_ports()

    own_ip = '1.1.1.1'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10000
    expected_rules = {
        SChainRule(port=10000, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10000, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10001, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10001, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10002, first_ip=None, last_ip=None),
        SChainRule(port=10003, first_ip=None, last_ip=None),
        SChainRule(port=10004, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10004, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10005, first_ip='2.2.2.2', last_ip=None),
        SChainRule(port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10005, first_ip='4.4.4.4', last_ip=None),
        SChainRule(port=10007, first_ip=None, last_ip=None),
        SChainRule(port=10008, first_ip=None, last_ip=None),
        SChainRule(port=10009, first_ip=None, last_ip=None),
        SChainRule(port=10010, first_ip=None, last_ip=None),
        SChainRule(port=10011, first_ip=None, last_ip=None),
        SChainRule(port=10012, first_ip=None, last_ip=None),
        SChainRule(port=10013, first_ip=None, last_ip=None)
    }
    src.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    new_own_ip = '2.2.2.2'
    new_node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '5.5.5.5']

    src.configure(own_ip=new_own_ip, node_ips=new_node_ips)

    expected_rules = {
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10000, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10001, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10001, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10002, first_ip=None, last_ip=None),
        SChainRule(port=10003, first_ip=None, last_ip=None),
        SChainRule(port=10004, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10004, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10005, first_ip='1.1.1.1', last_ip=None),
        SChainRule(port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(port=10005, first_ip='5.5.5.5', last_ip=None),
        SChainRule(port=10007, first_ip=None, last_ip=None),
        SChainRule(port=10008, first_ip=None, last_ip=None),
        SChainRule(port=10009, first_ip=None, last_ip=None),
        SChainRule(port=10010, first_ip=None, last_ip=None),
        SChainRule(port=10011, first_ip=None, last_ip=None),
        SChainRule(port=10012, first_ip=None, last_ip=None),
        SChainRule(port=10013, first_ip=None, last_ip=None)
    }
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []
