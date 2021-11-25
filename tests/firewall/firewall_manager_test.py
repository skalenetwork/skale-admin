import mock

from core.schains.firewall.types import SChainRule

from core.schains.firewall.firewall_manager import (
    SChainFirewallManager,
    IHostFirewallManager
)


class HostFirewallManagerMock(IHostFirewallManager):
    def __init__(self):
        self._rules = set()

    def add_rule(self, srule):
        self._rules.add(srule)

    def remove_rule(self, srule):
        if self.has_rule(srule):
            self._rules.remove(srule)

    @property
    def rules(self):
        return self._rules.__iter__()

    def has_rule(self, srule):
        return srule in self._rules


def test_firewall_manager():
    hm = HostFirewallManagerMock()
    fm = SChainFirewallManager('test', 10000, 10064, hm)
    assert list(fm.rules) == []
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001),
        SChainRule(10001, '3.3.3.3'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003)
    ]
    fm.add_rules(rules)
    assert list(sorted(fm.rules)) == rules, list(sorted(fm.rules))

    new_rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001),
        SChainRule(10001, '3.3.3.3'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10001, '4.4.4.4', '5.5.5.5'),
        SChainRule(10004)
    ]
    fm.update_rules(new_rules)
    assert list(sorted(fm.rules)) == new_rules

    rules_to_remove = list(fm.rules)[:-1]
    rules_to_remove.append(SChainRule(10005))
    fm.remove_rules(rules_to_remove)
    assert list(sorted(fm.rules)) == [new_rules[-1]]


def test_firewall_manager_update_existed():
    hm = HostFirewallManagerMock()
    fm = SChainFirewallManager('test', 10000, 10064, hm)
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003),
    ]
    fm.add_rules(rules)

    hm.add_rule = mock.Mock()
    hm.remove_rule = mock.Mock()
    fm.update_rules(rules)
    assert list(sorted(fm.rules)) == rules

    assert hm.add_rule.call_count == 0
    assert hm.remove_rule.call_count == 0


def test_firewall_manager_flush():
    hm = HostFirewallManagerMock()
    fm = SChainFirewallManager('test', 10000, 10064, hm)
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003),
    ]
    fm.add_rules(rules)
    hm.add_rule(SChainRule(10072, '2.2.2.2'))

    fm.flush()
    assert list(fm.rules) == []
    assert hm.has_rule(SChainRule(10072, '2.2.2.2'))
