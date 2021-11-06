from core.schains.firewall.rule_controller import (
    SChainRuleController,
    IFirewallManager,
    IpRange
)
from core.schains.firewall.entities import SChainRule, SkaledPorts


class FirewallManagerMock(IFirewallManager):
    def __init__(self):
        self._rules = set()

    @property
    def rules(self):
        return self._rules

    def update_rules(self, rules):
        self._rules = rules

    def add_rules(self, rules):
        for r in rules:
            self._rules.add(r)


def test_schain_rule_controller():
    tfm = FirewallManagerMock()
    own_ip = '3.3.3.3'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10064
    sync_ip_range = [
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
    src = SChainRuleController(
        tfm,
        base_port,
        own_ip,
        node_ips,
        SkaledPorts,
        sync_ip_range
    )
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync_rules()
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
    src.sync_rules()

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


def test_schain_rule_controller_no_sync_rules():
    tfm = FirewallManagerMock()
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
    src = SChainRuleController(
        tfm,
        base_port,
        own_ip,
        node_ips,
        SkaledPorts
    )
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync_rules()
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))
