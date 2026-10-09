import os
from unittest import mock

import pytest
from skale.schain_config import PORTS_PER_SCHAIN  # noqa

from core.firewall import (
    Action,
    SChainRule,
    get_fair_committee_scope_rule_controller,
    get_fair_network_scope_rule_controller,
)
from tools.helper import run_cmd


@pytest.fixture
def refresh():
    run_cmd(['nft', 'flush', 'ruleset'])
    try:
        yield
    finally:
        run_cmd(['nft', 'flush', 'ruleset'])


SSL_ON = 'core.firewall.fair.rule_controller.is_ssl_on'


@pytest.fixture
def ssl_on():
    with mock.patch(SSL_ON, return_value=True):
        yield


def test_network_scope_rule_controller(nft_chain_folder, ssl_on):
    own_ip = '3.3.3.3'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10000
    fair_network_expected_rules = []
    fair_committee_expected_rules = []

    fair_network_expected_rules = [
        SChainRule(first_port=10001, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_port=10005, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_port=10035, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_port=10040, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_ip='1.1.1.1', first_port=10001, action=Action.ACCEPT),
        SChainRule(first_ip='2.2.2.2', first_port=10001, action=Action.ACCEPT),
        SChainRule(first_ip='4.4.4.4', first_port=10001, action=Action.ACCEPT),
        SChainRule(first_port=10002, action=Action.ACCEPT),
        SChainRule(first_port=10003, action=Action.ACCEPT),
        SChainRule(first_ip='1.1.1.1', first_port=10005, action=Action.ACCEPT),
        SChainRule(first_ip='2.2.2.2', first_port=10005, action=Action.ACCEPT),
        SChainRule(first_ip='4.4.4.4', first_port=10005, action=Action.ACCEPT),
        SChainRule(first_port=10007, action=Action.ACCEPT),
        SChainRule(first_port=10008, action=Action.ACCEPT),
    ]

    fair_committee_expected_rules = [
        SChainRule(first_port=10000, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_port=10004, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_port=10011, action=Action.DROP, interface_exception='lo'),
        SChainRule(first_ip='1.1.1.1', first_port=10000, action=Action.ACCEPT),
        SChainRule(first_ip='2.2.2.2', first_port=10000, action=Action.ACCEPT),
        SChainRule(first_ip='4.4.4.4', first_port=10000, action=Action.ACCEPT),
        SChainRule(first_ip='1.1.1.1', first_port=10004, action=Action.ACCEPT),
        SChainRule(first_ip='2.2.2.2', first_port=10004, action=Action.ACCEPT),
        SChainRule(first_ip='4.4.4.4', first_port=10004, action=Action.ACCEPT),
        SChainRule(first_ip='1.1.1.1', first_port=10011, action=Action.ACCEPT),
        SChainRule(first_ip='2.2.2.2', first_port=10011, action=Action.ACCEPT),
        SChainRule(first_ip='4.4.4.4', first_port=10011, action=Action.ACCEPT),
    ]

    fair_network_expected_chain = 'chain fair-network {\n\ttype filter hook input priority filter; policy accept;\n\ttcp dport 10008 counter accept\n\ttcp dport 10007 counter accept\n\tip saddr 4.4.4.4 tcp dport 10005 counter accept\n\tip saddr 2.2.2.2 tcp dport 10005 counter accept\n\tip saddr 1.1.1.1 tcp dport 10005 counter accept\n\ttcp dport 10003 counter accept\n\ttcp dport 10002 counter accept\n\tip saddr 4.4.4.4 tcp dport 10001 counter accept\n\tip saddr 2.2.2.2 tcp dport 10001 counter accept\n\tip saddr 1.1.1.1 tcp dport 10001 counter accept\n\ttcp dport 10001 iifname != "lo" counter drop\n\ttcp dport 10005 iifname != "lo" counter drop\n\ttcp dport 10035 iifname != "lo" counter drop\n\ttcp dport 10040 iifname != "lo" counter drop\n}\n'  # noqa

    fair_committee_expected_chain = 'chain fair-committee {\n\ttype filter hook input priority filter; policy accept;\n\tip saddr 4.4.4.4 tcp dport 10011 counter accept\n\tip saddr 2.2.2.2 tcp dport 10011 counter accept\n\tip saddr 1.1.1.1 tcp dport 10011 counter accept\n\tip saddr 4.4.4.4 tcp dport 10004 counter accept\n\tip saddr 2.2.2.2 tcp dport 10004 counter accept\n\tip saddr 1.1.1.1 tcp dport 10004 counter accept\n\tip saddr 4.4.4.4 tcp dport 10000 counter accept\n\tip saddr 2.2.2.2 tcp dport 10000 counter accept\n\tip saddr 1.1.1.1 tcp dport 10000 counter accept\n\ttcp dport 10000 iifname != "lo" counter drop\n\ttcp dport 10004 iifname != "lo" counter drop\n\ttcp dport 10011 iifname != "lo" counter drop\n}\n'  # noqa

    for rc_create, expected_rules, expected_chain in zip(
        (get_fair_network_scope_rule_controller, get_fair_committee_scope_rule_controller),
        (fair_network_expected_rules, fair_committee_expected_rules),
        (fair_network_expected_chain, fair_committee_expected_chain),
    ):
        rc = rc_create(base_port, own_ip, node_ips)
        # Will create host controller and apply base config as a side effect
        assert rc.is_inited()

        chain_filepath = f'/etc/nft.conf.d/skale/chains/fair-{rc.name}.conf'
        assert os.path.isfile(chain_filepath)
        with open(chain_filepath) as chain_file:
            chain = chain_file.read()
            assert (
                chain
                == 'chain fair-'
                + rc.name
                + ' {\n\ttype filter hook input priority filter; policy accept;\n}\n'
            )  # noqa

        assert rc.is_persistent()
        assert rc.actual_rules() == []
        assert not rc.is_rules_synced()
        rc.sync()

        chain_filepath = f'/etc/nft.conf.d/skale/chains/fair-{rc.name}.conf'
        assert os.path.isfile(chain_filepath)
        with open(chain_filepath) as chain_file:
            chain = chain_file.read()
            assert chain == expected_chain

        assert rc.expected_rules() == rc.actual_rules()
        assert rc.is_rules_synced()
        rules = rc.actual_rules()
        assert rules == expected_rules

        hm = rc.firewall_manager.host_controller
        hm.add_rule = mock.Mock()
        hm.remove_rule = mock.Mock()
        rc.firewall_manager.update_rules(rules)

        assert hm.add_rule.call_count == 0
        assert hm.remove_rule.call_count == 0

        rc.cleanup()
        assert not rc.is_inited()
        assert not rc.is_persistent()


def test_network_scope_tls_ports_follow_certificates(nft_chain_folder):
    rc = get_fair_network_scope_rule_controller(10000, '3.3.3.3', ['1.1.1.1', '3.3.3.3'])
    tls_accepts = {SChainRule(first_port=port) for port in (10007, 10008)}
    tls_drops = {
        SChainRule(first_port=port, action=Action.DROP, interface_exception='lo')
        for port in (10007, 10008)
    }
    # skaled's own listeners behind nginx stay hidden whatever the certificates are
    proxied_drops = {
        SChainRule(first_port=port, action=Action.DROP, interface_exception='lo')
        for port in (10035, 10040)
    }

    with mock.patch(SSL_ON, return_value=False):
        rc.sync()
        assert rc.is_rules_synced()
        rules = set(rc.actual_rules())
        assert tls_drops | proxied_drops <= rules
        assert not tls_accepts & rules
        assert {SChainRule(first_port=10002), SChainRule(first_port=10003)} <= rules

    with mock.patch(SSL_ON, return_value=True):
        assert not rc.is_rules_synced()
        rc.sync()
        assert rc.is_rules_synced()
        rules = set(rc.actual_rules())
        assert tls_accepts | proxied_drops <= rules
        assert not tls_drops & rules
        assert rc.is_persistent()

    with mock.patch(SSL_ON, return_value=False):
        assert not rc.is_rules_synced()
        rc.sync()
        rules = set(rc.actual_rules())
        assert tls_drops <= rules
        assert not tls_accepts & rules

    rc.cleanup()
