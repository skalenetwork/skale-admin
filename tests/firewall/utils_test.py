import mock
import pytest

from core.schains.firewall.utils import get_default_rule_controller
from core.schains.firewall.types import IpRange
from tools.helper import run_cmd


@pytest.fixture
def refresh():
    run_cmd(['iptables', '-F'])
    try:
        yield
    finally:
        run_cmd(['iptables', '-F'])


def test_get_default_rule_controller():
    own_ip = '3.3.3.3'
    node_ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3', '4.4.4.4']
    base_port = 10064
    sync_ip_range = [
        IpRange(start_ip='10.10.10.10', end_ip='15.15.15.15'),
        IpRange(start_ip='15.15.15.15', end_ip='18.18.18.18')
    ]
    rc = get_default_rule_controller(
        'test',
        base_port,
        own_ip,
        node_ips,
        sync_ip_range
    )
    assert rc.actual_rules() == []
    rc.sync()
    assert rc.expected_rules() == rc.actual_rules()

    rules = rc.actual_rules()

    hm = rc.firewall_manager.host_manager
    hm.add_rule = mock.Mock()
    hm.remove_rule = mock.Mock()
    rc.firewall_manager.update_rules(rules)

    assert hm.add_rule.call_count == 0
    assert hm.remove_rule.call_count == 0
