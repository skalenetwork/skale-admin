from unittest import mock

import pytest

from core.firewall import LOOPBACK_INTERFACE, Action, IpRange, SChainRule, SkaledPorts
from core.firewall.schain.rule_controller import NotInitializedError
from tests.utils import SChainTestRuleController
from tools.constants import SSL_CERT_PATH, SSL_KEY_PATH

SSL_ON = 'core.firewall.schain.rule_controller.is_ssl_on'


@pytest.fixture
def ssl_on():
    with mock.patch(SSL_ON, return_value=True):
        yield


def test_schain_rule_controller(ssl_on):
    own_ip = '3.3.3.3'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10064
    sync_ip_ranges = [
        IpRange(start_ip='10.10.10.10', end_ip='15.15.15.15'),
        IpRange(start_ip='15.15.15.15', end_ip='18.18.18.18'),
    ]
    drop_rule = SChainRule(
        first_port=base_port,
        last_port=base_port + 63,
        action=Action.DROP,
        interface_exception=LOOPBACK_INTERFACE,
    )
    assert drop_rule < SChainRule(first_port=10064, first_ip='1.1.1.1', last_ip=None)

    expected_rules = {
        drop_rule,
        SChainRule(first_port=10064, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10064, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10064, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10065, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10065, first_ip='10.10.10.10', last_ip='15.15.15.15'),
        SChainRule(first_port=10065, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(first_port=10065, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10065, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10066, first_ip=None, last_ip=None),
        SChainRule(first_port=10067, first_ip=None, last_ip=None),
        SChainRule(first_port=10068, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10068, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10068, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10069, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10069, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10069, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10069, first_ip='10.10.10.10', last_ip='15.15.15.15'),
        SChainRule(first_port=10069, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(first_port=10071, first_ip=None, last_ip=None),
        SChainRule(first_port=10072, first_ip=None, last_ip=None),
        SChainRule(first_port=10074, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10074, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10074, first_ip='4.4.4.4', last_ip=None),
    }
    src = SChainTestRuleController(
        'test', base_port, own_ip, node_ips, SkaledPorts, sync_ip_ranges=sync_ip_ranges
    )
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    new_sync_ip_ranges = [
        IpRange(start_ip='15.15.15.15', end_ip='18.18.18.18'),
        IpRange(start_ip='20.20.20.20', end_ip='21.21.21.21'),
    ]
    new_node_ips = ['1.1.1.1', '5.5.5.5', '3.3.3.3', '4.4.4.4']
    src.sync_ip_ranges = new_sync_ip_ranges
    src.node_ips = new_node_ips
    assert not src.is_rules_synced()
    src.sync()
    drop_rule = SChainRule(
        first_port=base_port,
        last_port=base_port + 63,
        action=Action.DROP,
        interface_exception=LOOPBACK_INTERFACE,
    )

    expected_rules = {
        drop_rule,
        SChainRule(first_port=10064, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10064, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10064, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10065, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10065, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(first_port=10065, first_ip='20.20.20.20', last_ip='21.21.21.21'),
        SChainRule(first_port=10065, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10065, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10066, first_ip=None, last_ip=None),
        SChainRule(first_port=10067, first_ip=None, last_ip=None),
        SChainRule(first_port=10068, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10068, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10068, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10069, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10069, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10069, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10069, first_ip='15.15.15.15', last_ip='18.18.18.18'),
        SChainRule(first_port=10069, first_ip='20.20.20.20', last_ip='21.21.21.21'),
        SChainRule(first_port=10071, first_ip=None, last_ip=None),
        SChainRule(first_port=10072, first_ip=None, last_ip=None),
        SChainRule(first_port=10074, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10074, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10074, first_ip='5.5.5.5', last_ip=None),
    }
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []


def test_schain_rule_controller_no_sync_rules(ssl_on):
    own_ip = '1.1.1.1'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10000
    drop_rule = SChainRule(
        first_port=base_port,
        last_port=base_port + 63,
        action=Action.DROP,
        interface_exception=LOOPBACK_INTERFACE,
    )

    expected_rules = {
        drop_rule,
        SChainRule(first_port=10000, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10000, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10001, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10001, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10002, first_ip=None, last_ip=None),
        SChainRule(first_port=10003, first_ip=None, last_ip=None),
        SChainRule(first_port=10004, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10004, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10005, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10005, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10007, first_ip=None, last_ip=None),
        SChainRule(first_port=10008, first_ip=None, last_ip=None),
        SChainRule(first_port=10010, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10010, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10010, first_ip='4.4.4.4', last_ip=None),
    }
    src = SChainTestRuleController('test', base_port, own_ip, node_ips)
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []


def test_schain_rule_controller_configure(ssl_on):
    src = SChainTestRuleController('test')

    with pytest.raises(NotInitializedError):
        src.public_ports()

    own_ip = '1.1.1.1'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10000

    src.configure(base_port=base_port)
    with pytest.raises(NotInitializedError):
        src.public_ports()

    src.configure(base_port=base_port, node_ips=node_ips)
    assert list(src.public_ports) == [10003, 10002, 10008, 10007]
    drop_rule = SChainRule(
        first_port=base_port,
        last_port=base_port + 63,
        action=Action.DROP,
        interface_exception=LOOPBACK_INTERFACE,
    )
    expected_rules = {
        drop_rule,
        SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10000, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10000, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10001, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10001, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10001, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10002, first_ip=None, last_ip=None),
        SChainRule(first_port=10003, first_ip=None, last_ip=None),
        SChainRule(first_port=10004, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10004, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10004, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10005, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10005, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10005, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10007, first_ip=None, last_ip=None),
        SChainRule(first_port=10008, first_ip=None, last_ip=None),
        SChainRule(first_port=10010, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10010, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10010, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10010, first_ip='4.4.4.4', last_ip=None),
    }
    src.configure(base_port=base_port, node_ips=node_ips)

    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    src.sync()
    assert src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))
    assert list(src.actual_rules()) == list(sorted(expected_rules))

    expected_rules = {
        drop_rule,
        SChainRule(first_port=10000, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10000, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10001, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10001, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10002, first_ip=None, last_ip=None),
        SChainRule(first_port=10003, first_ip=None, last_ip=None),
        SChainRule(first_port=10004, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10004, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10005, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10005, first_ip='4.4.4.4', last_ip=None),
        SChainRule(first_port=10007, first_ip=None, last_ip=None),
        SChainRule(first_port=10008, first_ip=None, last_ip=None),
        SChainRule(first_port=10010, first_ip='2.2.2.2', last_ip=None),
        SChainRule(first_port=10010, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10010, first_ip='4.4.4.4', last_ip=None),
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
        drop_rule,
        SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10000, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10000, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10001, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10001, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10002, first_ip=None, last_ip=None),
        SChainRule(first_port=10003, first_ip=None, last_ip=None),
        SChainRule(first_port=10004, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10004, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10004, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10005, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10005, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10005, first_ip='5.5.5.5', last_ip=None),
        SChainRule(first_port=10007, first_ip=None, last_ip=None),
        SChainRule(first_port=10008, first_ip=None, last_ip=None),
        SChainRule(first_port=10010, first_ip='1.1.1.1', last_ip=None),
        SChainRule(first_port=10010, first_ip='3.3.3.3', last_ip=None),
        SChainRule(first_port=10010, first_ip='5.5.5.5', last_ip=None),
    }
    assert not src.is_rules_synced()
    assert list(src.expected_rules()) == list(sorted(expected_rules))

    src.cleanup()
    assert list(src.actual_rules()) == []


def test_schain_rule_controller_tls_ports_follow_certificates():
    base_port = 10000
    tls_rules = {SChainRule(first_port=10007), SChainRule(first_port=10008)}
    src = SChainTestRuleController('test', base_port, '1.1.1.1', ['1.1.1.1', '2.2.2.2'])

    with mock.patch(SSL_ON, return_value=False):
        assert list(src.public_ports) == [10003, 10002]
        src.sync()
        assert src.is_rules_synced()
        assert not tls_rules & set(src.actual_rules())

    with mock.patch(SSL_ON, return_value=True):
        assert not src.is_rules_synced()
        src.sync()
        assert src.is_rules_synced()
        assert tls_rules <= set(src.actual_rules())

    with mock.patch(SSL_ON, return_value=False):
        assert not src.is_rules_synced()
        src.sync()
        assert src.is_rules_synced()
        assert not tls_rules & set(src.actual_rules())

    src.cleanup()


def test_schain_rule_controller_reads_certificates_from_ssl_folder(ssl_folder):
    src = SChainTestRuleController('test', 10000, '1.1.1.1', ['1.1.1.1', '2.2.2.2'])
    try:
        assert list(src.public_ports) == [10003, 10002]
        SSL_CERT_PATH.touch()
        # half a pair is not a TLS setup yet
        assert list(src.public_ports) == [10003, 10002]
        SSL_KEY_PATH.touch()
        assert list(src.public_ports) == [10003, 10002, 10008, 10007]
    finally:
        SSL_CERT_PATH.unlink(missing_ok=True)
        SSL_KEY_PATH.unlink(missing_ok=True)
