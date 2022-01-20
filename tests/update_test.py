import mock
from core.node_config import NodeConfig
from core.updates import update_node_config_file


OLD_NODE_STRUCT = {
    'name': 'test',
    'ip': b'A\x80\x17\xe4'
}

NEW_NODE_STRUCT = {
    'name': 'new-test',
    'ip': b'\x01\x01\x01\x01'
}


def test_update_node_config_file(skale):
    config = NodeConfig()
    config.id = 0
    config.name = None
    config.ip = None

    assert config.id == 0
    assert config.name is None
    assert config.ip is None

    with mock.patch('skale.contracts.manager.nodes.Nodes.get',
                    new=mock.Mock(return_value=OLD_NODE_STRUCT)):
        update_node_config_file(skale, config)

    assert config.name == 'test'
    assert config.ip == '65.128.23.228'

    with mock.patch('skale.contracts.manager.nodes.Nodes.get',
                    new=mock.Mock(return_value=NEW_NODE_STRUCT)):
        update_node_config_file(skale, config)

    assert config.name == 'new-test'
    assert config.ip == '1.1.1.1'
