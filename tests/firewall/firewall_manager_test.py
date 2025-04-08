import mock

from core.schains.firewall.types import SChainRule

from tests.utils import SChainTestFirewallManager


def test_firewall_manager():
    fm = SChainTestFirewallManager('test', 10000, 10064)
    assert list(fm.rules) == []
    rules = [
        SChainRule(first_port=10000, first_ip='2.2.2.2'),
        SChainRule(first_port=10001),
        SChainRule(first_port=10001, first_ip='3.3.3.3'),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10003)
    ]
    fm.add_rules(rules)
    assert list(sorted(fm.rules)) == rules, list(sorted(fm.rules))

    new_rules = [
        SChainRule(first_port=10000, first_ip='2.2.2.2'),
        SChainRule(first_port=10001),
        SChainRule(first_port=10001, first_ip='3.3.3.3'),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10001, first_ip='4.4.4.4', last_ip='5.5.5.5'),
        SChainRule(first_port=10004)
    ]
    fm.update_rules(new_rules)
    assert list(sorted(fm.rules)) == new_rules

    rules_to_remove = list(fm.rules)[:-1]
    rules_to_remove.append(SChainRule(first_port=10005))
    fm.remove_rules(rules_to_remove)
    assert list(sorted(fm.rules)) == [new_rules[-1]]


def test_firewall_manager_update_existed():
    fm = SChainTestFirewallManager('test', 10000, 10064)
    rules = [
        SChainRule(first_port=10000, first_ip='2.2.2.2'),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10003),
    ]
    fm.add_rules(rules)

    fm.host_controller.add_rule = mock.Mock()
    fm.host_controller.remove_rule = mock.Mock()
    fm.update_rules(rules)
    assert list(sorted(fm.rules)) == rules

    assert fm.host_controller.add_rule.call_count == 0
    assert fm.host_controller.remove_rule.call_count == 0


def test_firewall_manager_cleanup():
    fm = SChainTestFirewallManager('test', 10000, 10064)
    rules = [
        SChainRule(first_port=10000, first_ip='2.2.2.2'),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10003),
    ]
    fm.add_rules(rules)
    fm.host_controller.add_rule(SChainRule(first_port=10072, last_ip='2.2.2.2'))

    fm.cleanup()
    assert list(fm.rules) == []
    assert fm.host_controller.has_rule(SChainRule(first_port=10072, last_ip='2.2.2.2'))
