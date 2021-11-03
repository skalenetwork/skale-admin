from core.schains.firewall.entities import SChainRule

from core.schains.firewall.firewall_manager import (
    SChainFirewallManager,
    IHostFirewallManager
)


class TestHostFirewallManager(IHostFirewallManager):
    def __init__(self):
        self._rules = set()
        pass

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
    hm = TestHostFirewallManager()
    fm = SChainFirewallManager('test', 10000, 10064, hm)
    assert list(fm.rules) == []
    rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '3.3.3.3', '4.4.4.4'),
        SChainRule(10003),
    ]
    fm.add_rules(rules)
    assert list(sorted(fm.rules)) == rules

    new_rules = [
        SChainRule(10000, '2.2.2.2'),
        SChainRule(10001, '4.4.4.4', '5.5.5.5'),
        SChainRule(10003)
    ]
    fm.update_rules(new_rules)
    assert list(sorted(fm.rules)) == new_rules

    rules_to_remove = list(fm.rules)[:-1]
    rules_to_remove.append(SChainRule(10004))
    fm.remove_rules(rules_to_remove)
    assert list(sorted(fm.rules)) == [rules[-1]]
