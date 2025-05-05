import mock

# Import types for mocking specs
from skale.types.rotation import Rotation
from skale.contracts.manager.schains import SchainStructure

# Import the target function and result class
from core.config.mirage.generator import generate_mirage_config
from core.config.base_config import MirageConfig


def test_generate_mirage_config_minimal_regular(schain_secret_key_file):
    mock_schain = mock.MagicMock(spec=SchainStructure)
    mock_schain.name = 'mirage'
    mock_schain.part_of_node = 1

    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node_id = 1
    common_bls_keys = ['0xA', '0xB']
    node_bls_keys = ['0xNodeA', '0xNodeB']

    schain_nodes_with_schains = {
        node_id: {
            'id': node_id,
            'name': f'{node_id}',
            'ip': '1.1.1.1',
            'basePort': 10000,
            'publicKey': '0xOwner1',
            'blsPublicKey': node_bls_keys,
            'schain': mock_schain,
        }
    }
    node_groups = {1700000000: {'nodes': {node_id: [0, 0, '0xOwner1']}}}

    config = generate_mirage_config(
        schain=mock_schain,
        schain_nodes_with_schains=schain_nodes_with_schains,
        node_groups=node_groups,
        rotation_data=mock_rotation,
        node_id=node_id,
        ecdsa_key_name='NEK:SIMPLE_REGULAR',
        schain_base_port=10000,
        common_bls_public_keys=common_bls_keys,
        sync_node=False,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()

    assert (
        config_dict['params']['chainID'] == '0x3A6'
    )  # TODO: replace this when we implement chainID lookup instead of hardcoding
    assert 'skaleConfig' in config_dict
    assert 'contractSettings' not in config_dict['skaleConfig']

    node_info = config_dict['skaleConfig']['nodeInfo']
    assert node_info['nodeID'] == node_id
    assert node_info['name'] == str(node_id)
    assert node_info['syncNode'] is False
    assert 'wallets' in node_info
    assert 'keyShareName' in node_info['wallets']

    schain_info = config_dict['skaleConfig']['sChain']
    assert schain_info['schainID'] == int('0x3A6', 16)
    assert schain_info['multiTransactionMode'] is True
    assert 'nodes' in schain_info
    first_ts_key = str(mock_rotation.freeze_until)
    assert first_ts_key in schain_info['nodes']
    node_list = schain_info['nodes'][first_ts_key]
    assert len(node_list) > 0
    assert 'publicKey' not in node_list[0]
    assert 'publicIP' not in node_list[0]


def test_generate_mirage_config_minimal_sync(schain_secret_key_file):
    mock_schain = mock.MagicMock(spec=SchainStructure)
    mock_schain.name = 'mirage'
    mock_schain.part_of_node = 1

    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node_id = 1
    common_bls_keys = ['0xA', '0xB']
    node_bls_keys = ['0xNodeA', '0xNodeB']

    schain_nodes_with_schains = {
        node_id: {
            'id': node_id,
            'name': f'node-{node_id}',
            'ip': '1.1.1.1',
            'basePort': 10000,
            'publicKey': '0xOwner1',
            'blsPublicKey': node_bls_keys,
            'schain': mock_schain,
        }
    }
    node_groups = {1700000000: {'nodes': {node_id: [0, 0, '0xOwner1']}}}

    config = generate_mirage_config(
        schain=mock_schain,
        schain_nodes_with_schains=schain_nodes_with_schains,
        node_groups=node_groups,
        rotation_data=mock_rotation,
        node_id=node_id,
        ecdsa_key_name='NEK:SIMPLE_SYNC',
        schain_base_port=12000,
        common_bls_public_keys=common_bls_keys,
        sync_node=True,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()

    node_info = config_dict['skaleConfig']['nodeInfo']
    assert node_info['syncNode'] is True

    assert 'wallets' in node_info
    wallets = node_info['wallets']
    assert wallets['n'] == len(common_bls_keys)
    assert 'keyShareName' not in wallets
    assert 't' not in wallets
    assert 'BLSPublicKey0' not in wallets
