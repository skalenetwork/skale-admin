from skale import SkaleManager
from skale.types.node import NodeId
from skale.types.schain import SchainHash, SchainName
from skale.utils.helper import ip_to_bytes

from core.manager_cache import ManagerCache
from core.node import (
    calc_reload_ts,
    get_current_ips,
    get_current_nodes,
    get_max_ip_change_ts,
    get_node_delay,
    get_node_index_in_group,
)
from tests.utils import generate_random_ip


def test_get_current_nodes(
    skale: SkaleManager,
    schain_hash_on_contracts: SchainHash,
    number_of_nodes: int,
    manager_cache: ManagerCache,
):
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts, manager_cache)
    assert len(current_nodes) == number_of_nodes


def test_get_current_ips(
    skale: SkaleManager,
    schain_hash_on_contracts: SchainHash,
    number_of_nodes: int,
    manager_cache: ManagerCache,
):
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts, manager_cache)
    current_ips = get_current_ips(current_nodes)
    assert len(current_ips) == number_of_nodes
    assert current_ips[0] == current_nodes[0]['ip']


def test_get_max_ip_change_ts(skale: SkaleManager, schain_hash_on_contracts: SchainHash):
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts)
    max_ip_change_ts = get_max_ip_change_ts(current_nodes)
    assert max_ip_change_ts is None
    new_ip = generate_random_ip()
    skale.nodes.change_ip(current_nodes[0]['id'], ip_to_bytes(new_ip), ip_to_bytes(new_ip))
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts)
    max_ip_change_ts = get_max_ip_change_ts(current_nodes)
    assert max_ip_change_ts is not None
    assert max_ip_change_ts > 0


def test_calc_reload_ts(skale: SkaleManager, schain_hash_on_contracts: SchainHash):
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts)
    reload_ts = calc_reload_ts(current_nodes, 4)
    assert reload_ts is None
    new_ip = generate_random_ip()
    skale.nodes.change_ip(current_nodes[0]['id'], ip_to_bytes(new_ip), ip_to_bytes(new_ip))
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts)
    max_ip_change_ts = get_max_ip_change_ts(current_nodes)

    reload_ts = calc_reload_ts(current_nodes, 4)
    assert max_ip_change_ts < reload_ts

    reload_ts = calc_reload_ts(current_nodes, 0)
    assert reload_ts == max_ip_change_ts + 300

    reload_ts = calc_reload_ts([{'ip_change_ts': 0}, {'ip_change_ts': 100}, {'ip_change_ts': 0}], 2)
    assert reload_ts == 1000


def test_get_node_index_in_group(
    skale: SkaleManager,
    schain_on_contracts: SchainName,
    schain_hash_on_contracts: SchainHash,
    manager_cache: ManagerCache,
):
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts, manager_cache)
    node_index = get_node_index_in_group(skale, schain_on_contracts, current_nodes[1]['id'])
    assert node_index == 1
    node_index = get_node_index_in_group(skale, schain_on_contracts, NodeId(99999999))
    assert node_index is None


def test_get_node_delay():
    assert get_node_delay(3) == 1200
    assert get_node_delay(0) == 300
    assert get_node_delay(16) == 5100
