import mock

from core.schains.process_manager import get_leaving_schains_for_node
from core.schains.runner import is_exited


def test_is_exited(dutils):
    schain_name = 'schain_test'
    info_mock = {
        'status': 'exited',
        'stats': {
            'State': {
                'ExitCode': 1
            }
        }
    }
    get_info = dutils.get_info
    try:
        dutils.get_info = mock.Mock(return_value=info_mock)
        assert is_exited(schain_name, dutils=dutils)
    finally:
        dutils.get_info = get_info


# TODO: improve test
def test_get_leaving_schains_for_node(skale, node_config):
    leaving_schains = get_leaving_schains_for_node(skale, node_config.id)
    assert isinstance(leaving_schains, list)
