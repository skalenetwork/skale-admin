import mock
from core.node_config import NodeConfig
from core.updates import update_node_config_file


def test_update_node_config_file(skale):
    config = NodeConfig()
    config.id = 0
    config.name = None

    assert config.id == 0
    assert config.name is None

    with mock.patch('skale.contracts.nodes.Nodes.get_active_node_ids_by_address',
                    new=mock.Mock(return_value=[3])):
        with mock.patch('skale.contracts.nodes.Nodes.get',
                        new=mock.Mock(return_value={'name': 'test'})):
            update_node_config_file(skale, config)

    assert config.id == 3
    assert config.name == 'test'
