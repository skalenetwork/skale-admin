from unittest import mock

from skale import SkaleManager

from core.chain.runner import is_exited
from core.manager_cache import get_leaving_schains_for_node
from core.node_config import NodeConfig


def test_is_exited(dutils):
    schain_name = 'schain_test'
    info_mock = {'status': 'exited', 'stats': {'State': {'ExitCode': 1}}}
    get_info = dutils.get_info
    try:
        dutils.get_info = mock.Mock(return_value=info_mock)
        assert is_exited(schain_name, dutils=dutils)
    finally:
        dutils.get_info = get_info


def test_get_leaving_schains_for_node(skale: SkaleManager, node_config: NodeConfig):
    leaving_schains = get_leaving_schains_for_node(skale, node_config.id)
    assert isinstance(leaving_schains, list)
