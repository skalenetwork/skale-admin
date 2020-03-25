import time
import subprocess
import concurrent.futures

import pytest

from tools.iptables import add_rules, apsent_rules, remove_rules, NodeEndpoint


def get_rules_through_plain_subprocess():
    result = subprocess.run(['iptables', '-S'],
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    stdout = result.stdout.decode('utf-8')
    return set(filter(lambda s: s, stdout.split('\n')))


def plain_rule_from_endpoint(endpoint):
    ip_str, port_str = ('', '')
    if endpoint.ip is not None:
        ip_str = f'-s {endpoint.ip}/32 '
    if endpoint.port is not None:
        port_str = f'-m tcp --dport {endpoint.port} '
    return '-A INPUT {}-p tcp {}-j ACCEPT'.format(ip_str, port_str)


def test_rules_manipulation():
    endpoints = [
        NodeEndpoint(ip='11.11.11.11', port='1111'),
        NodeEndpoint(ip='12.12.12.12', port=None),
        NodeEndpoint(ip=None, port='1313')
    ]
    # Check that all rules are apsent
    assert len(apsent_rules(endpoints)) == 3

    # Add rules
    add_rules(endpoints)

    # Check that all rules to add are successfully added
    plain_rules = get_rules_through_plain_subprocess()
    for endpoint in endpoints:
        plain_rule = plain_rule_from_endpoint(endpoint)
        assert plain_rule in plain_rules
    # Check that None of added rules are apsent
    assert apsent_rules(endpoints) == []

    # Remove one rule
    endpoints_to_remove = endpoints[2:]
    remove_rules(endpoints_to_remove)

    # Check that it is apsent
    assert len(apsent_rules(endpoints_to_remove)) == 1

    # Check that it was removed successfully
    plain_rules = get_rules_through_plain_subprocess()
    removed_plain_rule = plain_rule_from_endpoint(endpoints_to_remove[0])
    assert removed_plain_rule not in plain_rules

    endpoints.pop()

    # Check that all other rules are not apsent
    assert apsent_rules(endpoints) == []
    # Check that all other rules remain in iptables
    for endpoint in endpoints:
        plain_rule = plain_rule_from_endpoint(endpoint)
        assert plain_rule in plain_rules

    # Remove rest of the rules
    remove_rules(endpoints)
    # Check that they are apsent and removed successfully
    assert len(apsent_rules(endpoints)) == 2
    plain_rules = get_rules_through_plain_subprocess()
    for endpoint in endpoints:
        plain_rule = plain_rule_from_endpoint(endpoint)
        assert plain_rule not in plain_rules


@pytest.mark.skip('Problems with github actions')
def test_add_in_threads():
    def add_remove_rule(endpoint):
        add_rules([endpoint])
        time.sleep(1)
        remove_rules([endpoint])

    endpoints = [
        NodeEndpoint(ip='11.11.11.11', port='1111'),
        NodeEndpoint(ip='12.12.12.12', port='1212'),
        NodeEndpoint(ip='13.13.13.13', port='1313'),
        NodeEndpoint(ip='14.14.14.14', port='1414'),
        NodeEndpoint(ip='15.15.15.15', port='1515')
    ]
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for endpoint in endpoints:
            future = executor.submit(add_remove_rule, endpoint)
            futures.append(future)

    for future in futures:
        print(future.result)

    assert len(apsent_rules(endpoints)) == len(endpoints)
