import concurrent.futures
import importlib
import os
import time

import pytest

from core.schains.firewall.nftables import NFTablesController, NFT_CHAIN_BASE_PATH
from core.schains.firewall.types import SChainRule
from core.schains.firewall.utils import cleanup_firewall_for_schain
from tools.helper import run_cmd


@pytest.fixture
def nf_test_tables():
    nft = importlib.import_module('nftables').Nftables()
    nft.cmd('flush ruleset')
    return nft


@pytest.fixture
def filter_table(nf_test_tables):
    print(nf_test_tables.cmd('add table inet firewall'))


@pytest.fixture
def custom_chain(nf_test_tables, filter_table):
    name = 'test-chain'
    nf_test_tables.cmd(f'add chain inet firewall skale-{name}')
    return name


def test_nftables_controller(custom_chain):
    nft_controller = NFTablesController(chain='test-chain')
    rule_a = SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    rule_b = SChainRule(first_port=10001, first_ip='3.3.3.3')
    nft_controller.add_rule(rule_a)
    nft_controller.add_rule(rule_b)
    assert nft_controller.has_rule(rule_a)
    assert nft_controller.has_rule(rule_b)
    rules = list(nft_controller.rules)
    assert sorted(rules) == sorted([rule_b, rule_a]), (rules, sorted([rule_b, rule_a]))
    nft_controller.remove_rule(rule_a)
    assert not nft_controller.has_rule(rule_a)
    assert nft_controller.has_rule(rule_b)
    nft_controller.remove_rule(rule_b)
    assert not nft_controller.has_rule(rule_a)


def test_nftables_controller_duplicates(custom_chain):
    rule_a = SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    manager = NFTablesController(chain='test-chain')
    manager.add_rule(rule_a)
    rule_b = SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4')
    manager.add_rule(rule_b)
    assert sorted(list(manager.rules)) == sorted([
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ])
    assert manager.has_rule(rule_b)
    manager.add_rule(rule_b)
    assert manager.has_rule(rule_b)
    assert sorted(list(manager.rules)) == sorted([
        SChainRule(first_port=10001, first_ip='3.3.3.3', last_ip='4.4.4.4'),
        SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ])
    manager.remove_rule(rule_b)
    assert list(manager.rules) == [
        SChainRule(first_port=10000, first_ip='1.1.1.1', last_ip='2.2.2.2')
    ]


def test_create_delete_chain(filter_table, nft_chain_folder):
    chain_name = 'test-chain'

    output = run_cmd(['nft', 'list', 'chains']).stdout.decode('utf-8')
    output == 'table inet firewall {\n}\n'
    nft_chain_path = os.path.join(NFT_CHAIN_BASE_PATH, f'skale-{chain_name}.conf')
    assert not os.path.isfile(nft_chain_path)

    manager = NFTablesController(chain=chain_name)
    manager.create_chain(first_port=10000, last_port=10063)

    chains = run_cmd(['nft', 'list', 'chains']).stdout.decode('utf-8')
    assert chains == 'table inet firewall {\n\tchain skale-test-chain {\n\t\ttype filter hook input priority filter; policy accept;\n\t}\n}\n'  # noqa
    assert os.path.isfile(nft_chain_path)

    manager.cleanup()
    chains = run_cmd(['nft', 'list', 'chains']).stdout.decode('utf-8')
    assert chains == 'table inet firewall {\n}\n'
    assert os.path.isfile(nft_chain_path)

    manager.remove_saved_rules()
    assert not os.path.isfile(nft_chain_path)


def test_saved_rules(filter_table, nft_chain_folder):
    chain_name = 'test-chain'
    nft_chain_path = os.path.join(NFT_CHAIN_BASE_PATH, f'skale-{chain_name}.conf')

    manager = NFTablesController(chain=chain_name)
    assert not os.path.isfile(nft_chain_path)
    manager.create_chain(first_port=10000, last_port=10063)
    assert os.path.isfile(nft_chain_path)
    print('HERE', manager.get_saved_rules())
    assert manager.get_saved_rules() == 'chain skale-test-chain {\n\ttype filter hook input priority filter; policy accept;\n\tiifname != "lo" tcp dport 10000-10063 counter drop\n}\n'  # noqa

    assert os.path.isfile(nft_chain_path)

    manager.remove_saved_rules()
    assert not os.path.isfile(nft_chain_path)


def test_cleanup_firewall_for_schain(filter_table, nft_chain_folder):
    chain_name = 'test-chain'
    nft_chain_path = os.path.join(NFT_CHAIN_BASE_PATH, f'skale-{chain_name}.conf')

    manager = NFTablesController(chain=chain_name)
    manager.create_chain(first_port=10000, last_port=10063)

    cleanup_firewall_for_schain(schain_name=chain_name)
    chains = run_cmd(['nft', 'list', 'chains']).stdout.decode('utf-8')
    assert chains == 'table inet firewall {\n}\n'
    assert not os.path.isfile(nft_chain_path)


def add_remove_rule(srule, refresh):
    manager = NFTablesController(chain='test')
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
            first_port=10000 + 1,
            first_ip=f'{i}.{i}.{i}.{i}', last_ip=f'{i + 1}.{i + 1}.{i + 1}.{i + 1}'
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
