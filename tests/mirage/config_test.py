import pytest
import mock
import os
import json
from pathlib import Path

from core.config.mirage.generator import generate_mirage_config
from core.config.base_config import MirageConfig

from skale.types.rotation import Rotation
from skale.contracts.manager.schains import SchainStructure

from tools.configs.schains import SCHAINS_DIR_PATH

MIRAGE_TEST_SECRET_KEY = {
    'key_share_name': 'BLS_KEY:SCHAIN_ID:MIRAGE:NODE_ID:0:DKG_ID:0',
    't': 1,
    'n': 2,
    'common_public_key': (['0xA'], ['0xB']),
    'public_key': ['0xNodeA', '0xNodeB'],
    'bls_public_keys': ['0xNodeA:1:2:3', '0xNodeB:4:5:6'],
}


@pytest.fixture
def mirage_secret_key_file():
    """Creates a dummy secret_key_0.json specifically for mirage tests."""
    schain_name = 'mirage'
    schain_dir = os.path.join(SCHAINS_DIR_PATH, schain_name)
    secret_key_path = os.path.join(schain_dir, 'secret_key_0.json')

    try:
        Path(schain_dir).mkdir(parents=True, exist_ok=True)
        with open(secret_key_path, 'w') as f:
            json.dump(MIRAGE_TEST_SECRET_KEY, f)
        yield
    finally:
        if os.path.exists(secret_key_path):
            os.remove(secret_key_path)
        try:
            os.rmdir(schain_dir)
        except OSError:
            pass


def test_generate_mirage_config_minimal_regular(mirage_secret_key_file):
    mock_schain = mock.MagicMock(spec=SchainStructure)
    mock_schain.name = 'mirage'
    mock_schain.part_of_node = 1

    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node_id = 1
    common_bls_keys = ['0xA', '0xB']

    node_bls_keys_for_node_info = ['0xNodeA', '0xNodeB']

    schain_nodes_with_schains = [
        {
            'id': 1,
            'name': 'node-1',
            'ip': b'\x01\x01\x01\x01',
            'publicIP': b'\x01\x01\x01\x01',
            'port': 10000,
            'publicKey': '0x' + 'a' * 128,
            'blsPublicKey': node_bls_keys_for_node_info
            if node_id == 1
            else ['0xOtherA', '0xOtherB'],
            'schains': [mock_schain],
        },
        {
            'id': 2,
            'name': 'node-2',
            'ip': b'\x02\x02\x02\x02',
            'publicIP': b'\x02\x02\x02\x02',
            'port': 11000,
            'publicKey': '0x' + 'b' * 128,
            'blsPublicKey': node_bls_keys_for_node_info
            if node_id == 2
            else ['0xOtherA', '0xOtherB'],
            'schains': [mock_schain],
        },
    ]

    node_groups = {
        1700000000: {'nodes': {1: [0, 0, '0x' + 'a' * 128], 2: [1, 1, '0x' + 'b' * 128]}}
    }

    config = generate_mirage_config(
        schain=mock_schain,
        schain_nodes_with_schains=schain_nodes_with_schains,
        node_groups=node_groups,
        rotation_data=mock_rotation,
        node_id=node_id,
        ecdsa_key_name='NEK:SIMPLE_REGULAR',
        schain_base_port=12000,
        common_bls_public_keys=common_bls_keys,
        sync_node=False,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()

    assert config_dict['params']['chainID'] == '0x3A6'
    assert 'skaleConfig' in config_dict
    assert 'contractSettings' not in config_dict['skaleConfig']

    node_info = config_dict['skaleConfig']['nodeInfo']
    assert node_info['nodeID'] == node_id
    assert node_info['nodeName'] == str(node_id)
    assert node_info['syncNode'] is False
    assert 'wallets' in node_info
    assert 'keyShareName' in node_info['wallets']
    assert node_info['wallets']['BLSPublicKey0'] == node_bls_keys_for_node_info[0]

    schain_info = config_dict['skaleConfig']['sChain']
    assert schain_info['schainID'] == int('0x3A6', 16)
    assert schain_info['multiTransactionMode'] is True
    assert 'nodes' in schain_info

    ts_key = mock_rotation.freeze_until
    assert ts_key in schain_info['nodes']
    node_list = schain_info['nodes'][ts_key]
    assert len(node_list) == 2
    assert 'publicKey' not in node_list[0]
    assert 'publicIP' not in node_list[0]
    assert node_list[0]['owner'].startswith('0x')


def test_generate_mirage_config_minimal_sync(mirage_secret_key_file):
    mock_schain = mock.MagicMock(spec=SchainStructure)
    mock_schain.name = 'mirage'
    mock_schain.part_of_node = 1

    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node_id = 1
    common_bls_keys = ['0xA', '0xB']

    schain_nodes_with_schains = [
        {
            'id': 1,
            'name': 'node-1',
            'ip': b'\x01\x01\x01\x01',
            'publicIP': b'\x01\x01\x01\x01',
            'port': 10000,
            'publicKey': '0x' + 'a' * 128,
            'blsPublicKey': [],
            'schains': [mock_schain],
        },
        {
            'id': 2,
            'name': 'node-2',
            'ip': b'\x02\x02\x02\x02',
            'publicIP': b'\x02\x02\x02\x02',
            'port': 11000,
            'publicKey': '0x' + 'b' * 128,
            'blsPublicKey': [],
            'schains': [mock_schain],
        },
    ]

    node_groups = {
        1700000000: {'nodes': {1: [0, 0, '0x' + 'a' * 128], 2: [1, 1, '0x' + 'b' * 128]}}
    }

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
