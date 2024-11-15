import concurrent.futures
import importlib
import time

import pytest

from core.schains.firewall.nftables import NFTablesController
from core.schains.firewall.types import SChainRule


@pytest.fixture
def nf_test_tables():
    nft = importlib.import_module('nftables').NFTables()
    nft.cmd('flush ruleset')
    return nft


@pytest.fixture
def filter_table(nf_test_tables):
    print(nf_test_tables.cmd('add table inet filter'))


@pytest.fixture
def custom_chain(nf_test_tables, filter_table):
    nf_test_tables.cmd('add chain inet filter test-chain')
    return 'test-chain'


def test_nftables_controller(custom_chain):
    nft_controller = NFTablesController(chain='test-chain')
    rule_a = SChainRule(10000, '1.1.1.1', '2.2.2.2')
    rule_b = SChainRule(10001, '3.3.3.3')
    nft_controller.add_rule(rule_a)
    nft_controller.add_rule(rule_b)
    assert nft_controller.has_rule(rule_a)
    assert nft_controller.has_rule(rule_b)
    rules = list(nft_controller.rules)
    assert rules == sorted([rule_b, rule_a])
    nft_controller.remove_rule(rule_a)
    assert not nft_controller.has_rule(rule_a)
    assert nft_controller.has_rule(rule_b)
    nft_controller.remove_rule(rule_b)
    assert not nft_controller.has_rule(rule_a)


def test_nftables_controller_duplicates(custom_chain):
    rule_a = SChainRule(10000, '1.1.1.1', '2.2.2.2')
    manager = NFTablesController(chain='test-chain')
    manager.add_rule(rule_a)
    rule_b = SChainRule(10001, '3.3.3.3', '4.4.4.4')
    manager.add_rule(rule_b)
    assert sorted(list(manager.rules)) == sorted([
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ])
    assert manager.has_rule(rule_b)
    manager.add_rule(rule_b)
    assert manager.has_rule(rule_b)
    assert sorted(list(manager.rules)) == sorted([
        SChainRule(port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ])
    manager.remove_rule(rule_b)
    assert list(manager.rules) == [
        SChainRule(port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ]


def add_remove_rule(srule, refresh):
    manager = NFTablesController()
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


def test_nftables_manager_parallel(custom_chain):
    srules = generate_srules(number=12)

    futures = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=12) as executor:
        futures = [
            executor.submit(add_remove_rule, srule)
            for srule in srules
        ]

        for future in concurrent.futures.as_completed(futures):
            assert future.result
    manager = NFTablesController(custom_chain)
    time.sleep(10)
    assert len(list(manager.rules)) == 0
