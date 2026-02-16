import json
import os
from pathlib import Path
from unittest import mock

import pytest
from config_controller_predeployed import (
    CONFIG_CONTROLLER_ADDRESS,
    CONFIG_CONTROLLER_IMPLEMENTATION_ADDRESS,
)
from eth_typing import BlockNumber, HexStr
from etherbase_predeployed.address import ETHERBASE_ADDRESS, ETHERBASE_IMPLEMENTATION_ADDRESS
from filestorage_predeployed import FILESTORAGE_ADDRESS, FILESTORAGE_IMPLEMENTATION_ADDRESS
from ima_predeployed.generator import MESSAGE_PROXY_FOR_SCHAIN_ADDRESS
from marionette_predeployed.address import MARIONETTE_ADDRESS, MARIONETTE_IMPLEMENTATION_ADDRESS
from multisigwallet_predeployed.address import MULTISIGWALLET_ADDRESS
from skale import SkaleIma, SkaleManager
from skale.dataclasses.schain_options import AllocationType
from skale.types.node import Node, NodeId, NodeStatus, NodeWithSchainHashes, Port
from skale.types.rotation import NodeGroups, Rotation, RotationNodeData
from skale.types.schain import SchainName, SchainStructure
from skale.types.validator import ValidatorId
from skale.utils.helper import schain_name_to_hash
from skale.utils.web3_utils import to_checksum_address
from web3 import Web3

from core.config.base import FairConfig
from core.config.schain.generator import (
    generate_schain_config,
    generate_schain_config_with_skale,
    get_ima_contracts_addresses,
    get_schain_originator,
)
from core.config.schain.helper import get_schain_id
from core.config.schain.predeployed import PROXY_ADMIN_PREDEPLOYED_ADDRESS
from core.node_config import NodeConfig
from tests.utils import TEST_MAINNET_OWNER_ADDRESS, TEST_ORIGINATOR_ADDRESS, get_schain_struct
from tools.constants.schains import SCHAINS_DIR_PATH
from tools.node_options import NodeOptions

NODE_ID = NodeId(1)
ECDSA_KEY_NAME = 'TEST:KEY:NAME'
COMMON_BLS_PUBLIC_KEY: list[str] = ['123', '456', '789', '123']
SCHAIN_NAME = SchainName('test_schain')
EMPTY_NODE_GROUPS: NodeGroups = {}

SECRET_KEY = {
    'key_share_name': 'BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0',
    't': 3,
    'n': 4,
    'common_public_key': COMMON_BLS_PUBLIC_KEY,
    'public_key': ['123', '456', '789', '123'],
    'bls_public_keys': [
        '347043388985314611088523723672849261459066865147342514766975146031592968981:16865625797537152485129819826310148884042040710059790347821575891945447848787:12298029821069512162285775240688220379514183764628345956323231135392667898379:8',
        '347043388985314611088523723672849261459066865147342514766975146031592968982:16865625797537152485129819826310148884042040710059790347821575891945447848788:12298029821069512162285775240688220379514183764628345956323231135392667898380:9',
    ],
}

NODE_GROUPS: NodeGroups = {
    2: {
        'rotation': {
            'leaving_node_id': NodeId(0),
            'new_node_id': NodeId(5),
        },
        'nodes': {
            NodeId(4): RotationNodeData(4, NodeId(31), '0x5d'),
            NodeId(5): RotationNodeData(8, NodeId(179), '0xon'),
        },
        'finish_ts': 1681498775,
        'bls_public_key': {
            'blsPublicKey0': '9',
            'blsPublicKey1': '1',
            'blsPublicKey2': '3',
            'blsPublicKey3': '2',
        },
    },
    1: {
        'rotation': {
            'leaving_node_id': NodeId(3),
            'new_node_id': NodeId(4),
        },
        'nodes': {
            NodeId(0): RotationNodeData(0, NodeId(159), '0xgd'),
            NodeId(4): RotationNodeData(4, NodeId(31), '0x5d'),
        },
        'finish_ts': 1681390775,
        'bls_public_key': {
            'blsPublicKey0': '3',
            'blsPublicKey1': '4',
            'blsPublicKey2': '7',
            'blsPublicKey3': '9',
        },
    },
    0: {
        'rotation': {
            'leaving_node_id': NodeId(2),
            'new_node_id': NodeId(3),
        },
        'nodes': {
            NodeId(0): RotationNodeData(0, NodeId(159), '0xgd'),
            NodeId(3): RotationNodeData(7, NodeId(61), '0xbh'),
        },
        'finish_ts': None,
        'bls_public_key': None,
    },
}

TEST_NODE: Node = {
    'name': 'test',
    'ip': b'\x01\x02\x03\x04',
    'publicIP': b'\x01\x02\x03\x04',
    'publicKey': HexStr('0x0B5e3eBB74eE281A24DDa3B1A4e70692c15EAC34'),
    'port': Port(10000),
    'start_block': BlockNumber(0),
    'last_reward_date': 0,
    'finish_time': 0,
    'status': NodeStatus.ACTIVE,
    'validator_id': ValidatorId(0),
    'domain_name': 'test.com',
}


def get_schain_struct_no_originator() -> SchainStructure:
    schain = get_schain_struct(_test_schain_name=SCHAIN_NAME)
    schain.originator = to_checksum_address('0x0000000000000000000000000000000000000000')
    return schain


def get_schain_struct_static_account() -> SchainStructure:
    schain = get_schain_struct(_test_schain_name='static_chain')
    return schain


def get_schain_nodes_with_schain_hashes(schain_name: SchainName) -> list[NodeWithSchainHashes]:
    schain_hash = schain_name_to_hash(schain_name)
    return [
        {
            'name': 'test',
            'ip': b'\x01\x02\x03\x04',
            'publicIP': b'\x01\x02\x03\x04',
            'publicKey': HexStr('0x0B5e3eBB74eE281A24DDa3B1A4e70692c15EAC34'),
            'port': Port(10000),
            'id': NodeId(1),
            'start_block': BlockNumber(0),
            'last_reward_date': 0,
            'finish_time': 0,
            'status': NodeStatus.ACTIVE,
            'validator_id': ValidatorId(0),
            'domain_name': 'test.com',
            'schain_hashes': [schain_hash],
        }
    ]


@pytest.fixture
def schain_secret_key_file(schain_on_contracts):
    schain_name = schain_on_contracts
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    Path(schain_dir_path).mkdir(exist_ok=True)
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    try:
        yield
    finally:
        Path(secret_key_path).unlink()
        Path(schain_dir_path).rmdir()


@pytest.fixture
def schain_secret_key_file_default_chain():
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, SCHAIN_NAME)
    Path(schain_dir_path).mkdir(exist_ok=True)
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    try:
        yield
    finally:
        Path(secret_key_path).unlink()
        Path(schain_dir_path).rmdir()


def test_get_ima_contracts_addresses(skale_ima):
    ima_addresses = get_ima_contracts_addresses(skale_ima)
    expected_keys = [
        'community_pool_address',
        'deposit_box_eth_address',
        'deposit_box_erc20_address',
        'deposit_box_erc721_address',
        'deposit_box_erc1155_address',
        'deposit_box_erc721_with_metadata_address',
        'linker_address',
    ]

    assert isinstance(ima_addresses, dict)
    assert all(key in ima_addresses for key in expected_keys)

    for key in expected_keys:
        assert Web3.is_checksum_address(ima_addresses[key])


def check_keys(data, expected_keys):
    assert all(key in data for key in expected_keys)


def check_node_ports(info):
    base_port = info['basePort']
    assert isinstance(base_port, int)
    assert info['wsRpcPort'] == base_port + 2
    assert info['wssRpcPort'] == base_port + 7
    assert info['httpRpcPort'] == base_port + 3
    assert info['httpsRpcPort'] == base_port + 8


def check_node_bls_keys(info, index):
    bls_keys = SECRET_KEY['bls_public_keys'][index].split(':')
    assert info['blsPublicKey0'] == bls_keys[0]
    assert info['blsPublicKey1'] == bls_keys[1]
    assert info['blsPublicKey2'] == bls_keys[2]
    assert info['blsPublicKey3'] == bls_keys[3]


def check_node_info(node_id, info):
    keys = [
        'nodeID',
        'nodeName',
        'basePort',
        'httpRpcPort',
        'httpsRpcPort',
        'wsRpcPort',
        'wssRpcPort',
        'bindIP',
        'logLevel',
        'logLevelConfig',
        'ecdsaKeyName',
        'wallets',
        'minCacheSize',
        'maxCacheSize',
        'collectionQueueSize',
        'collectionDuration',
        'transactionQueueSize',
        'maxOpenLeveldbFiles',
        'info-acceptors',
        'syncNode',
        'pg-threads',
        'pg-threads-limit',
    ]

    check_keys(info, keys)
    assert info['nodeID'] == node_id
    check_node_ports(info)
    assert info['ecdsaKeyName'] == ECDSA_KEY_NAME


def check_schain_node_info(node_id, schain_node_info, index):
    check_keys(
        schain_node_info,
        [
            'nodeID',
            'nodeName',
            'basePort',
            'httpRpcPort',
            'httpsRpcPort',
            'wsRpcPort',
            'wssRpcPort',
            'publicKey',
            'blsPublicKey0',
            'blsPublicKey1',
            'blsPublicKey2',
            'blsPublicKey3',
            'owner',
            'schainIndex',
            'ip',
            'publicIP',
        ],
    )
    assert schain_node_info['nodeID'] == node_id
    check_node_ports(schain_node_info)
    check_node_bls_keys(schain_node_info, index)


def check_schain_info(node_ids, schain_info):
    check_keys(
        schain_info,
        [
            'schainID',
            'schainName',
            'blockAuthor',
            'contractStorageLimit',
            'dbStorageLimit',
            'snapshotIntervalSec',
            'emptyBlockIntervalMs',
            'maxConsensusStorageBytes',
            'maxSkaledLeveldbStorageBytes',
            'maxFileStorageBytes',
            'maxReservedStorageBytes',
            'nodes',
            'revertableFSPatchTimestamp',
            'contractStoragePatchTimestamp',
        ],
    )
    for index, (nid, schain_node_info) in enumerate(zip(node_ids, schain_info['nodes'])):
        check_schain_node_info(nid, schain_node_info, index)


def check_config(node_id, all_node_ids, config):
    check_keys(config, ['sealEngine', 'params', 'unddos', 'genesis', 'accounts', 'skaleConfig'])
    assert config['params']['skaleDisableChainIdCheck'] is True
    check_node_info(node_id, config['skaleConfig']['nodeInfo'])
    check_schain_info(all_node_ids, config['skaleConfig']['sChain'])


def test_generate_schain_config_with_skale(
    skale: SkaleManager,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    schain_on_contracts: SchainName,
    schain_secret_key_file,
):
    schain_name = schain_on_contracts
    schain = skale.schains.get_by_name(schain_name)
    node_ids = skale.schains_internal.node_ids_for_schain(schain_name)
    current_node_id = node_ids[0]
    node_config.id = current_node_id

    rotation_data = Rotation(
        leaving_node_id=NodeId(1), new_node_id=NodeId(0), freeze_until=0, rotation_counter=0
    )

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        ecdsa_key_name=ECDSA_KEY_NAME,
        generation=0,
        node_options=NodeOptions(),
    )
    check_config(current_node_id, node_ids, schain_config.to_dict())


def test_generate_schain_config_gen0(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 0, 0
    ecdsa_key_name = 'test'

    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct(_test_schain_name=SCHAIN_NAME),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['sChain']['blockAuthor'] == TEST_MAINNET_OWNER_ADDRESS
    assert not config['accounts'].get(TEST_ORIGINATOR_ADDRESS)


def test_generate_schain_config_gen1(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct(_test_schain_name=SCHAIN_NAME),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=True,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    block_author = config['skaleConfig']['sChain']['blockAuthor']

    assert block_author == ETHERBASE_ADDRESS
    assert config['accounts'][TEST_ORIGINATOR_ADDRESS] == {
        'balance': '1000000000000000000000000000000'
    }

    assert config['accounts'].get(MARIONETTE_ADDRESS)
    assert config['accounts'].get(MARIONETTE_IMPLEMENTATION_ADDRESS)
    assert config['accounts'].get(FILESTORAGE_ADDRESS)
    assert config['accounts'].get(FILESTORAGE_IMPLEMENTATION_ADDRESS)
    assert config['accounts'].get(ETHERBASE_ADDRESS)
    assert config['accounts'].get(ETHERBASE_IMPLEMENTATION_ADDRESS)
    assert config['accounts'].get(CONFIG_CONTROLLER_ADDRESS)
    assert config['accounts'].get(CONFIG_CONTROLLER_IMPLEMENTATION_ADDRESS)
    assert config['accounts'].get(MULTISIGWALLET_ADDRESS)
    assert config['accounts'].get(MESSAGE_PROXY_FOR_SCHAIN_ADDRESS)
    assert config['accounts'].get(PROXY_ADMIN_PREDEPLOYED_ADDRESS)

    assert not config['accounts'].get(TEST_MAINNET_OWNER_ADDRESS)


def test_generate_schain_config_gen1_pk_owner(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert not config['accounts'].get(TEST_ORIGINATOR_ADDRESS)
    assert config['accounts'].get(TEST_MAINNET_OWNER_ADDRESS)


def test_generate_schain_config_gen2_schain_id(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 2, 0
    ecdsa_key_name = 'test'
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 2755779573749746


def test_generate_schain_config_gen1_schain_id(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name='test',
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 1


def test_generate_schain_config_gen0_schain_id(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 0, 0
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name='test',
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 1


def test_generate_schain_config_allocation_type(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'

    schain = get_schain_struct(_test_schain_name=SCHAIN_NAME)
    schain.options.allocation_type = AllocationType.NO_FILESTORAGE

    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=True,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['maxConsensusStorageBytes'] == 94904996659
    assert config['skaleConfig']['sChain']['maxSkaledLeveldbStorageBytes'] == 94904996659
    assert config['skaleConfig']['sChain']['maxFileStorageBytes'] == 0

    schain = get_schain_struct(_test_schain_name=SCHAIN_NAME)
    schain.options.allocation_type = AllocationType.MAX_CONSENSUS_DB

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=True,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['maxConsensusStorageBytes'] == 151847994654
    assert config['skaleConfig']['sChain']['maxSkaledLeveldbStorageBytes'] == 37961998663
    assert config['skaleConfig']['sChain']['maxFileStorageBytes'] == 0


def test_generate_schain_config_with_skale_gen2(
    skale: SkaleManager,
    skale_ima: SkaleIma,
    schain_on_contracts: SchainName,
    schain_secret_key_file,
    node_config: NodeConfig,
):
    schain_name = schain_on_contracts
    schain = skale.schains.get_by_name(schain_name)
    node_ids = skale.schains_internal.node_ids_for_schain(schain_name)
    current_node_id = node_ids[0]
    node_config.id = current_node_id

    rotation_data = Rotation(
        leaving_node_id=NodeId(1), new_node_id=NodeId(0), freeze_until=0, rotation_counter=0
    )

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        ecdsa_key_name=ECDSA_KEY_NAME,
        generation=2,
    )
    schain_config_dict = schain_config.to_dict()
    check_config(current_node_id, node_ids, schain_config_dict)
    assert schain_config_dict['skaleConfig']['sChain']['schainID'] == get_schain_id(schain_name)


def test_generate_schain_config_with_dynamic_pricing(
    skale_ima: SkaleIma,
    schain_secret_key_file_default_chain,
):
    node_id, generation, rotation_id = NodeId(1), 2, 0
    ecdsa_key_name = 'test'
    min_price_int = 100000
    max_price_int = 200000

    schain = get_schain_struct(SCHAIN_NAME)
    schain.options.min_gas_price = min_price_int
    schain.options.max_gas_price = max_price_int
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    node_info = config['skaleConfig']['nodeInfo']
    assert node_info['dynamicPricingMinPrice'] == min_price_int
    assert node_info['dynamicPricingStartPrice'] == min_price_int
    assert node_info['dynamicPricingMaxPrice'] == max_price_int


def test_get_schain_originator():
    originator = get_schain_originator(get_schain_struct_no_originator())
    assert originator == TEST_MAINNET_OWNER_ADDRESS

    originator = get_schain_originator(get_schain_struct(_test_schain_name=SCHAIN_NAME))
    assert originator == TEST_ORIGINATOR_ADDRESS


def test_generate_passive_node_config(schain_secret_key_file_default_chain, skale_ima):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'
    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo']['syncNode']
    assert config['skaleConfig']['sChain']['dbStorageLimit'] == 12653999554


def test_generate_passive_node_config_archive_catchup(
    schain_secret_key_file_default_chain, skale_ima
):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'

    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert not config['skaleConfig']['nodeInfo'].get('syncFromCatchup')
    assert not config['skaleConfig']['nodeInfo'].get('archiveMode')

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        archive=False,
        catchup=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo'].get('syncFromCatchup')
    assert config['skaleConfig']['nodeInfo'].get('archiveMode') is False

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=False,
        archive=False,
        catchup=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo'].get('syncFromCatchup') is None
    assert config['skaleConfig']['nodeInfo'].get('archiveMode') is None

    schain_config = generate_schain_config(
        schain=get_schain_struct_no_originator(),
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(SCHAIN_NAME),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        archive=True,
        catchup=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo'].get('syncFromCatchup')
    assert config['skaleConfig']['nodeInfo'].get('archiveMode')


def test_generate_passive_node_config_static_accounts(
    schain_secret_key_file_default_chain, skale_ima
):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'

    contracts_addresses = get_ima_contracts_addresses(skale_ima)
    schain = get_schain_struct_static_account()

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(
            SchainName('static_chain')
        ),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert config['accounts'].get('0x1111111')
    assert config['accounts']['0x1111111']['balance'] == '1000000000000000000000000000000'

    schain = get_schain_struct(_test_schain_name='other_schain')

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(schain.name),
        node_groups=EMPTY_NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()
    assert not config['accounts'].get('0x1111111')


def test_generate_config_static_groups(
    _schain_name,
    schain_secret_key_file_default_chain,
    static_groups_for_schain,
    skale_ima,
):
    node_id, generation, rotation_id = NodeId(1), 1, 0
    ecdsa_key_name = 'test'

    schain = get_schain_struct(_test_schain_name=_schain_name)
    schain.mainnet_owner = TEST_MAINNET_OWNER_ADDRESS
    schain.originator = TEST_ORIGINATOR_ADDRESS
    schain.options.multitransaction_mode = True

    contracts_addresses = get_ima_contracts_addresses(skale_ima)

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        rotation_id=rotation_id,
        schain_nodes_with_schain_hashes=get_schain_nodes_with_schain_hashes(_schain_name),
        node_groups=NODE_GROUPS,
        generation=generation,
        is_owner_contract=False,
        common_bls_public_keys=COMMON_BLS_PUBLIC_KEY,
        schain_base_port=10000,
        passive_node=True,
        mainnet_ima_addresses=contracts_addresses,
    )
    config = schain_config.to_dict()

    config_group = config['skaleConfig']['sChain']['nodeGroups']
    assert len(config_group.keys()) == 3
    for rotation_id_string in static_groups_for_schain:
        rotation_id = int(rotation_id_string)
        assert json.dumps(config_group[rotation_id]) == json.dumps(
            static_groups_for_schain[rotation_id_string]
        )


@mock.patch('core.config.schain.generator.is_fair', (lambda: True))
@mock.patch('core.config.fair.generator.generate_fair_config')
@mock.patch('core.config.schain.generator.generate_schain_config')
def test_generate_schain_config_with_skale_calls_fair(
    mock_generate_standard,
    mock_generate_fair,
    skale: SkaleManager,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    schain_on_contracts: SchainName,
    schain_secret_key_file,
):
    schain_name = schain_on_contracts
    schain = skale.schains.get_by_name(schain_name)
    node_ids = skale.schains_internal.node_ids_for_schain(schain_name)
    current_node_id = node_ids[0]
    node_config.id = current_node_id

    rotation_data = Rotation(
        leaving_node_id=NodeId(1), new_node_id=NodeId(0), freeze_until=0, rotation_counter=0
    )

    mock_generate_fair.return_value = mock.MagicMock(spec=FairConfig)

    result = generate_schain_config_with_skale(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        generation=2,
        node_config=node_config,
        rotation_data=rotation_data,
        ecdsa_key_name=ECDSA_KEY_NAME,
        passive_node=False,
        node_options=NodeOptions(),
    )

    mock_generate_fair.assert_called_once()
    mock_generate_standard.assert_not_called()
    assert isinstance(result, FairConfig)
