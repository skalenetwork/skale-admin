import mock
import pytest
import concurrent.futures

from skale.schain_config import PORTS_PER_SCHAIN  # noqa

from core.schains.firewall import IptablesController
from core.schains.firewall.utils import get_default_rule_controller
from core.schains.firewall.types import IpRange, SkaledPorts
from tests.firewall.iptables_test import get_rules_through_subprocess
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

    hm = rc.firewall_manager.host_controller
    hm.add_rule = mock.Mock()
    hm.remove_rule = mock.Mock()
    rc.firewall_manager.update_rules(rules)

    assert hm.add_rule.call_count == 0
    assert hm.remove_rule.call_count == 0


def sync_rules(*args):
    rc = get_default_rule_controller(*args)
    if not rc.is_rules_synced():
        rc.sync()
        return True
    return False


def parse_plain_rule(plain_rule):
    first_ip, last_ip, port = None, None, None
    pr = plain_rule.split()
    if '--src-range' in pr:
        srange = pr[11]
        first_ip, last_ip = srange.split('-')
        port = pr[7]
    elif '-s' in pr:
        first_ip = last_ip = pr[3][:-3]
        port = pr[9]
    elif '--dport' in pr:
        port = pr[7]

    return first_ip, last_ip, int(port)


def run_concurrent_rc_syncing(
    node_number,
    schain_number,
    own_ip,
    workers,
    sync_agent_ranges_number,
    attempt=0,
    refresh=False
):
    base_ports = [
        10000 + PORTS_PER_SCHAIN * i
        for i in range(schain_number)
    ]
    schain_names = [f'test-{i}' for i in range(schain_number)]
    node_ips = [f'{i}.{i}.{i}.{i}' for i in range(1, node_number + 1)]
    sync_agent_ranges = [
        IpRange(
            f'{i + 1}.{i + 2}.{i + 3}.{i + 3}',
            f'{i + 1}.{i + 2}.{i + 3}.{i + 4}'
        )
        for i in range(sync_agent_ranges_number)
    ]
    schain_rule_configs = [
        (schain, base_port, own_ip, node_ips, sync_agent_ranges)
        for schain, base_port in zip(schain_names, base_ports)
    ]
    internal_ports = [
        base_port + offset
        for offset in [
            SkaledPorts.PROPOSAL.value,
            SkaledPorts.BINARY_CONSENSUS.value
        ]
        for base_port in base_ports
    ]
    catchup_ports = [
        base_port + SkaledPorts.CATCHUP.value
        for base_port in base_ports
    ]
    zmq_ports = [
        base_port + SkaledPorts.ZMQ_BROADCAST.value
        for base_port in base_ports
    ]
    public_ports = [
        base_port + offset
        for offset in (
            SkaledPorts.HTTP_JSON.value,
            SkaledPorts.HTTPS_JSON.value,
            SkaledPorts.WS_JSON.value,
            SkaledPorts.WSS_JSON.value,
            SkaledPorts.INFO_HTTP_JSON.value
        )
        for base_port in base_ports
    ]

    futures = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers
    ) as executor:
        futures = [
            executor.submit(sync_rules, *src)
            for src in schain_rule_configs
        ]
        for future in concurrent.futures.as_completed(futures):
            r = future.result(timeout=5)
            if refresh:
                assert r
            else:
                if attempt == 0:
                    assert r
                else:
                    assert not r

    pr = get_rules_through_subprocess(unique=False)[3:]
    rules = [parse_plain_rule(r) for r in pr]

    c = IptablesController()
    # Check that all ip rules are there
    for ip in node_ips:
        if ip != own_ip:
            assert sum(
                map(lambda x: x[0] == ip, rules)
            ) == 4 * schain_number, ip
            assert sum(
                map(lambda x: x.first_ip == ip, c.rules)
            ) == 4 * schain_number, ip

    # Check that all internal ports rules are there except CATCHUP
    for p in internal_ports:
        assert sum(map(lambda x: x[2] == p, rules)) == node_number - 1, p
        assert sum(map(lambda x: x.port == p, c.rules)) == node_number - 1, p

    # Check CATCHUP rules including sync agents rules
    catchup_e_number = node_number + sync_agent_ranges_number - 1
    for p in catchup_ports:
        assert sum(map(lambda x: x[2] == p, rules)) == catchup_e_number, p
        assert sum(map(lambda x: x.port == p, c.rules)) == catchup_e_number, p

    # Check ZMQ rules including sync agents rules
    zmq_e_number = node_number + sync_agent_ranges_number - 1
    for p in zmq_ports:
        assert sum(map(lambda x: x[2] == p, rules)) == zmq_e_number, p
        assert sum(map(lambda x: x.port == p, c.rules)) == zmq_e_number, p

    # Check sync ip ranges rules
    for r in sync_agent_ranges:
        assert sum(
            map(lambda x: x[0] == r.start_ip, rules)
        ) == schain_number, ip
        assert sum(
            map(lambda x: x.first_ip == r.start_ip, c.rules)
        ) == schain_number, ip
        assert sum(
            map(lambda x: x[1] == r.end_ip, rules)
        ) == schain_number, ip
        assert sum(
            map(lambda x: x.last_ip == r.end_ip, c.rules)
        ) == schain_number, ip

    for port in public_ports:
        assert sum(map(lambda x: x[2] == port, rules)) == 1, port
        assert sum(map(lambda x: x.port == port, c.rules)) == 1, port


@pytest.mark.parametrize('attempt', range(5))
def test_concurrent_rc_behavior_no_refresh(attempt):
    node_number = 16
    schain_number = 8
    own_ip = '1.1.1.1'
    sync_agent_ranges_number = 5
    run_concurrent_rc_syncing(
        node_number,
        schain_number,
        own_ip,
        workers=schain_number,
        sync_agent_ranges_number=sync_agent_ranges_number,
        attempt=attempt
    )


@pytest.mark.parametrize('attempt', range(5))
def test_concurrent_rc_behavior_with_refresh(attempt, refresh):
    node_number = 16
    schain_number = 8
    own_ip = '1.1.1.1'
    sync_agent_ranges_number = 5
    run_concurrent_rc_syncing(
        node_number,
        schain_number,
        own_ip,
        workers=schain_number,
        sync_agent_ranges_number=sync_agent_ranges_number,
        attempt=attempt,
        refresh=True
    )
