import contextlib
import json
import os
from pathlib import Path
from typing import Dict, cast

import mock
import pytest
from eth_typing import BlockNumber, ChecksumAddress, HexStr
from skale.contracts.manager.schains import SchainStructure
from skale.types.node import MirageNode, Node, NodeId, NodeStatus, NodeWithSchains, Port
from skale.types.rotation import NodesGroup, NodesSwap, Rotation, RotationNodeData
from skale.types.validator import ValidatorId
from skale.types.committee import Timestamp, Committee
from skale.types.dkg import G2Point, DkgId, Fp2Point

from core.config.base import MirageConfig
from core.config.mirage.generator import generate_mirage_config, generate_mirage_config_adapter
from core.config.schain.helper import get_static_params_mirage as original_get_static_params_mirage
from tests.utils import CURRENT_TS
from tools.configs import MIRAGE_STATIC_PARAMS_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.web3 import ZERO_ADDRESS

MIRAGE_TEST_SECRET_KEY = {
    'key_share_name': 'BLS_KEY:SCHAIN_ID:MIRAGE:NODE_ID:0:DKG_ID:0',
    't': 1,
    'n': 2,
    'common_public_key': (['0xA'], ['0xB']),
    'public_key': ['0xNodeA', '0xNodeB'],
    'bls_public_keys': ['0xNodeA:1:2:3', '0xNodeB:4:5:6'],
}


@pytest.fixture
def committee_info_from_mirage_manager(mirage_node):
    committee_info_from_manager = [
        {
            'ts': 0,
            'index': 0,
            'group': [mirage_node, mirage_node],
            'committee': Committee(
                node_ids=[mirage_node.id, mirage_node.id],
                dkg_id=DkgId(0),
                common_public_key=G2Point(Fp2Point(a=1, b=2), Fp2Point(a=3, b=4)),
                starting_timestamp=Timestamp(0),
            ),
        },
        {
            'ts': CURRENT_TS,
            'index': 0,
            'group': [mirage_node, mirage_node],
            'committee': Committee(
                node_ids=[mirage_node.id, mirage_node.id],
                dkg_id=DkgId(0),
                common_public_key=G2Point(Fp2Point(a=1, b=2), Fp2Point(a=3, b=4)),
                starting_timestamp=Timestamp(0),
            ),
        },
    ]
    return committee_info_from_manager


@contextlib.contextmanager
def create_dynamic_secret_key_file(chain_name_for_path: str):
    """Context manager to create and clean up a dummy secret_key_0.json."""
    schain_dir = os.path.join(SCHAINS_DIR_PATH, chain_name_for_path)
    secret_key_path = os.path.join(schain_dir, 'secret_key_0.json')

    Path(schain_dir).mkdir(parents=True, exist_ok=True)
    with open(secret_key_path, 'w') as f:
        json.dump(MIRAGE_TEST_SECRET_KEY, f)
    try:
        yield secret_key_path
    finally:
        if os.path.exists(secret_key_path):
            os.remove(secret_key_path)
        try:
            if not os.listdir(schain_dir):
                os.rmdir(schain_dir)
        except OSError:
            pass


@pytest.fixture
def mirage_default_secret_key_file():
    """
    Creates a dummy secret_key_0.json specifically for mirage tests.
    Assumes env is exported devnet.
    """
    schain_name = 'mirage-devnet'
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


@pytest.fixture
def mirage_node():
    return MirageNode(
        id=NodeId(1),
        name='0xNodeA',
        ip=b'\x01\x01\x01\x01',
        ip_str='0x01\x01\x01\x01',
        domain_name='0xNodeA.com',
        address=ChecksumAddress(ZERO_ADDRESS),
        port=Port(10000),
        public_key=HexStr('0x' + 'a' * 128),
    )


@pytest.fixture
def node_groups() -> Dict[int, NodesGroup]:
    return {
        1700000000: {
            'nodes': {
                NodeId(1): RotationNodeData(0, 0, '0x' + 'a' * 128),
                NodeId(2): RotationNodeData(1, 1, '0x' + 'a' * 128),
            },
            'rotation': NodesSwap(leaving_node_id=NodeId(1), new_node_id=NodeId(2)),
            'finish_ts': 1000000000,
            'bls_public_key': None,
        }
    }


def test_generate_mirage_config_adapter(mirage_default_secret_key_file, node_groups):
    mock_schain = mock.MagicMock(spec=SchainStructure)
    mock_schain.name = 'mirage'
    mock_schain.part_of_node = 1

    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node = Node(
        name='0xNodeA',
        ip=b'\x01\x01\x01\x01',
        publicIP=b'\x01\x01\x01\x01',
        port=Port(10000),
        start_block=BlockNumber(0),
        last_reward_date=0,
        finish_time=0,
        status=NodeStatus.ACTIVE,
        validator_id=ValidatorId(1),
        publicKey=HexStr('0x' + 'a' * 128),
        domain_name='0xNodeA.com',
    )

    node_id = NodeId(1)

    node_bls_keys_for_node_info = ['0xNodeA', '0xNodeB']

    schain_nodes_with_schains = [
        {
            'id': 1,
            'name': 'node-1',
            'ip': b'\x01\x01\x01\x01',
            'publicIP': b'\x01\x01\x01\x01',
            'port': 10000,
            'blsPublicKey': node_bls_keys_for_node_info
            if node_id == 1
            else ['0xOtherA', '0xOtherB'],
            'schains': [mock_schain],
            'domain_name': '0xNodeA.com',
            'start_block': 0,
            'last_reward_date': 0,
            'finish_time': 0,
            'status': NodeStatus.ACTIVE,
            'validator_id': ValidatorId(1),
            'publicKey': HexStr('0x' + 'a' * 128),
        },
        {
            'id': 2,
            'name': 'node-2',
            'ip': b'\x02\x02\x02\x02',
            'publicIP': b'\x02\x02\x02\x02',
            'port': Port(11000),
            'blsPublicKey': node_bls_keys_for_node_info
            if node_id == 2
            else ['0xOtherA', '0xOtherB'],
            'schains': [mock_schain],
            'domain_name': '0xNodeA.com',
            'start_block': 0,
            'last_reward_date': 0,
            'finish_time': 0,
            'status': NodeStatus.ACTIVE,
            'validator_id': ValidatorId(1),
            'publicKey': HexStr('0x' + 'a' * 128),
        },
    ]

    config = generate_mirage_config_adapter(
        skale_node=node,
        node_id=node_id,
        chain_start_ts=CURRENT_TS,
        schain_nodes_with_schains=cast(list[NodeWithSchains], schain_nodes_with_schains),
        node_groups=node_groups,
        ecdsa_key_name='NEK:SIMPLE_REGULAR',
        sync_node=False,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()
    assert config_dict['params']['chainID'] == '0x3A8'


def test_generate_mirage_config_minimal_regular(
    mirage_default_secret_key_file, mirage_node, node_groups, committee_info_from_mirage_manager
):
    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    node_id = 1

    config = generate_mirage_config(
        node=mirage_node,
        committee_info_from_manager=committee_info_from_mirage_manager,
        node_groups=node_groups,
        ecdsa_key_name='NEK:SIMPLE_REGULAR',
        is_committee_node=True,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()

    assert config_dict['params']['chainID'] == '0x3A8'
    assert 'skaleConfig' in config_dict
    assert 'contractSettings' not in config_dict['skaleConfig']

    node_info = config_dict['skaleConfig']['nodeInfo']
    assert node_info['nodeID'] == node_id
    assert node_info['nodeName'] == str(node_id)
    assert node_info['syncNode'] is False

    schain_info = config_dict['skaleConfig']['sChain']
    assert schain_info['schainID'] == 936
    assert schain_info['multiTransactionMode'] is True
    assert 'nodes' in schain_info

    node_list = schain_info['nodes']
    assert len(node_list) == 2


def test_generate_mirage_config_minimal_sync(
    committee_info_from_mirage_manager, mirage_default_secret_key_file, mirage_node, node_groups
):
    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    config = generate_mirage_config(
        node=mirage_node,
        committee_info_from_manager=committee_info_from_mirage_manager,
        node_groups=node_groups,
        ecdsa_key_name='NEK:SIMPLE_REGULAR',
        is_committee_node=False,
        archive=False,
        catchup=False,
    )

    assert isinstance(config, MirageConfig)
    config_dict = config.to_dict()

    node_info = config_dict['skaleConfig']['nodeInfo']
    assert node_info['syncNode'] is True


@pytest.mark.parametrize(
    'current_env_type, expected_chain_id_hex, expected_chain_id_int, expected_chain_name',
    [
        ('mainnet', '0x3A6', 934, 'mirage'),
        ('testnet', '0x3A7', 935, 'mirage-testnet'),
        ('qanet', '0x3A9', 937, 'mirage-qa'),
        ('devnet', '0x3A8', 936, 'mirage-devnet'),
    ],
)
def test_generate_mirage_config_for_different_env_types(
    current_env_type,
    expected_chain_id_hex,
    expected_chain_id_int,
    expected_chain_name,
    mirage_node,
    committee_info_from_mirage_manager,
    node_groups,
):
    mock_rotation = mock.MagicMock(spec=Rotation)
    mock_rotation.rotation_counter = 0
    mock_rotation.freeze_until = 1700000000

    def replacement_get_static_params_mirage(
        env_type_arg_passed_by_caller, path_arg_passed_by_caller=MIRAGE_STATIC_PARAMS_FILEPATH
    ):
        return original_get_static_params_mirage(
            env_type=current_env_type, path=path_arg_passed_by_caller
        )

    with create_dynamic_secret_key_file(expected_chain_name):
        with mock.patch(
            'core.config.schain.static_params.get_static_params_mirage',
            new=replacement_get_static_params_mirage,
        ):
            config = generate_mirage_config(
                node=mirage_node,
                committee_info_from_manager=committee_info_from_mirage_manager,
                node_groups=node_groups,
                ecdsa_key_name='NEK:SIMPLE_REGULAR',
                is_committee_node=True,
                archive=False,
                catchup=False,
            )

            assert isinstance(config, MirageConfig)
            config_dict = config.to_dict()

    assert config_dict['params']['chainID'] == expected_chain_id_hex

    assert config_dict['skaleConfig']['sChain']['schainID'] == expected_chain_id_int

    assert config_dict['skaleConfig']['sChain']['schainName'] == expected_chain_name
