import time
import subprocess
import concurrent.futures

import pytest

from core.schains.firewall.iptables import IptablesManager
from core.schains.firewall.entities import SChainRule
from tools.helper import run_cmd


def get_rules_through_subprocess(unique=True):
    cmd_result = run_cmd(['iptables', '-S'])
    # cmd_result = subprocess.run(['iptables', '-S'],
    #                             stderr=subprocess.PIPE,
    #                             stdout=subprocess.PIPE)
    stdout = cmd_result.stdout.decode('utf-8')
    result = filter(lambda s: s, stdout.split('\n'))
    if unique:
        return set(result)
    else:
        return list(result)


def plain_from_schain_rule(srule):
    if srule.first_ip != srule.last_ip and \
            all((srule.first_ip, srule.last_ip)):
        return f'-A INPUT -p tcp -m tcp --dport {srule.port} -m iprange --src-range {srule.first_ip}-{srule.last_ip} -j ACCEPT'  # noqa
    elif srule.first_ip is not None:
        return f'-A INPUT -s {srule.first_ip}/32 -p tcp -m tcp --dport {srule.port} -j ACCEPT'  # noqa
    return f'-A INPUT -p tcp -m tcp --dport {srule.port} -j ACCEPT'


@pytest.fixture
def refresh():
    run_cmd(['iptables', '-F'])
    try:
        yield
    finally:
        run_cmd(['iptables', '-F'])


def test_iptables_manager(refresh):
    manager = IptablesManager()
    rule = SChainRule(10000, '1.1.1.1', '2.2.2.2')
    manager.add_rule(rule)
    assert manager.has_rule(rule)
    rules = list(manager.rules)
    assert rules == [rule]
    manager.remove_rule(rule)
    assert not manager.has_rule(rule)


def test_iptables_manager_add_duplicates(refresh):
    rule_a = SChainRule(10000, '1.1.1.1', '2.2.2.2')
    manager = IptablesManager()
    manager.add_rule(rule_a)
    rule_b = SChainRule(10001, '3.3.3.3', '4.4.4.4')
    manager.add_rule(rule_b)
    assert list(manager.rules) == [
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ]
    assert manager.has_rule(rule_b)
    manager.add_rule(rule_b)
    assert manager.has_rule(rule_b)
    assert list(manager.rules) == [
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ]
    manager.remove_rule(rule_b)
    assert list(manager.rules) == [
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ]
    plain_rules = get_rules_through_subprocess()
    plain_from_schain_rule(rule_b) not in plain_rules


def test_iptables_manager_correctly_process_old_rules(refresh):
    iptables_lines = """
    iptables -A INPUT -p tcp -m tcp --dport 10009 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 10007 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 10008 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 10002 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 10003 -j ACCEPT
    iptables -A INPUT -s 1.1.1.1/32 -p tcp -m tcp --dport 10005 -j ACCEPT
    iptables -A INPUT -s 1.1.1.1/32 -p tcp -m tcp --dport 10004 -j ACCEPT
    iptables -A INPUT -s 1.1.1.1/32 -p tcp -m tcp --dport 10001 -j ACCEPT
    iptables -A INPUT -s 1.1.1.1/32 -p tcp -m tcp --dport 10000 -j ACCEPT
    iptables -A INPUT -s 2.2.2.2/32 -p tcp -m tcp --dport 10005 -j ACCEPT
    iptables -A INPUT -s 2.2.2.2/32 -p tcp -m tcp --dport 10004 -j ACCEPT
    iptables -A INPUT -s 2.2.2.2/32 -p tcp -m tcp --dport 10001 -j ACCEPT
    iptables -A INPUT -s 2.2.2.2/32 -p tcp -m tcp --dport 10000 -j ACCEPT
    iptables -A INPUT -s 3.3.3.3/32 -p tcp -m tcp --dport 10005 -j ACCEPT
    iptables -A INPUT -s 3.3.3.3/32 -p tcp -m tcp --dport 10004 -j ACCEPT
    iptables -A INPUT -s 3.3.3.3/32 -p tcp -m tcp --dport 10001 -j ACCEPT
    iptables -A INPUT -s 3.3.3.3/32 -p tcp -m tcp --dport 10000 -j ACCEPT
    iptables -A INPUT -p udp -m udp --dport 53 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 9100 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 3009 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 53 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 443 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 8080 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 311 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
    iptables -A INPUT -p tcp -m tcp --dport 80 -j ACCEPT
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A INPUT -p icmp -m icmp --icmp-type 3 -j ACCEPT
    iptables -A INPUT -p icmp -m icmp --icmp-type 4 -j ACCEPT
    iptables -A INPUT -p icmp -m icmp --icmp-type 11 -j ACCEPT
    iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    iptables -A INPUT -p tcp -j DROP
    iptables -A INPUT -p udp -j DROP
    """

    cmds = map(lambda c: c.strip().split(), iptables_lines.split('\n'))
    for cmd in cmds:
        if cmd:
            subprocess.run(cmd)

    manager = IptablesManager()

    public_ports = [10002, 10003, 10007, 10008, 10009]
    for port in public_ports:
        assert manager.has_rule(SChainRule(port)), port

    internal_ports = [10000, 10001, 10004, 10005]
    ips = ['1.1.1.1', '2.2.2.2', '3.3.3.3']
    for port, ip in zip(internal_ports, ips):
        assert manager.has_rule(SChainRule(port, ip, ip)), (port, ip)

    srule_a = SChainRule(port=10000, first_ip='4.4.4.4')
    srule_b = SChainRule(port=10064, first_ip='5.5.5.5', last_ip='10.10.10.10')
    manager.add_rule(srule_a)
    manager.add_rule(srule_b)
    plain_rules = get_rules_through_subprocess()
    assert plain_from_schain_rule(srule_a) in plain_rules
    assert plain_from_schain_rule(srule_b) in plain_rules


def add_remove_rule(srule, refresh):
    manager = IptablesManager()
    manager.add_rule(srule)
    time.sleep(1)
    if not manager.has_rule(srule):
        return False
    time.sleep(1)
    manager.remove_rule(srule)
    return True


def generate_srules(number=5):
    return [
        SChainRule(
            10000 + 1,
            f'{i}.{i}.{i}.{i}', f'{i + 1}.{i + 1}.{i + 1}.{i + 1}'
        )
        for i in range(1, number * 2, 2)
    ]


def test_iptables_manager_parallel(refresh):
    srules = generate_srules(number=12)

    futures = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=12) as executor:
        futures = [
            executor.submit(add_remove_rule, srule)
            for srule in srules
        ]

        for future in concurrent.futures.as_completed(futures):
            assert future.result
    manager = IptablesManager()
    time.sleep(10)
    assert len(list(manager.rules)) == 0
