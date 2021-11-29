import mock

from core.schains.firewall.types import SChainRule

from tests.utils import SChainTestFirewallManager


def test_firewall_manager():
    fm = SChainTestFirewallManager('test', 10000, 10064)
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
    fm = SChainTestFirewallManager('test', 10000, 10064)
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003),
    ]
    fm.add_rules(rules)

    fm.host_controller.add_rule = mock.Mock()
    fm.host_controller.remove_rule = mock.Mock()
    fm.update_rules(rules)
    assert list(sorted(fm.rules)) == rules

    assert fm.host_controller.add_rule.call_count == 0
    assert fm.host_controller.remove_rule.call_count == 0


def test_firewall_manager_flush():
    fm = SChainTestFirewallManager('test', 10000, 10064)
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003),
    ]
    fm.add_rules(rules)
    fm.host_controller.add_rule(SChainRule(10072, '2.2.2.2'))

    fm.flush()
    assert list(fm.rules) == []
    assert fm.host_controller.has_rule(SChainRule(10072, '2.2.2.2'))
