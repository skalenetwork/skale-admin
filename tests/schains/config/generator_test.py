import json
import os
from pathlib import Path

import pytest
from etherbase_predeployed import ETHERBASE_ADDRESS, ETHERBASE_IMPLEMENTATION_ADDRESS
from marionette_predeployed import MARIONETTE_ADDRESS, MARIONETTE_IMPLEMENTATION_ADDRESS
from filestorage_predeployed import FILESTORAGE_ADDRESS, FILESTORAGE_IMPLEMENTATION_ADDRESS
from config_controller_predeployed import (
    CONFIG_CONTROLLER_ADDRESS,
    CONFIG_CONTROLLER_IMPLEMENTATION_ADDRESS
)
from multisigwallet_predeployed import MULTISIGWALLET_ADDRESS
from ima_predeployed.generator import MESSAGE_PROXY_FOR_SCHAIN_ADDRESS

from core.schains.config.generator import (
    generate_schain_config_with_skale, generate_schain_config, get_schain_originator
)
from core.schains.config.helper import get_schain_id
from core.schains.config.predeployed import PROXY_ADMIN_PREDEPLOYED_ADDRESS
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.node_options import NodeOptions


NODE_ID = 1
ECDSA_KEY_NAME = 'TEST:KEY:NAME'

SECRET_KEY = {
    "key_share_name": "BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0",
    "t": 3,
    "n": 4,
    "common_public_key": [123, 456, 789, 123],
    "public_key": [
        "123",
        "456",
        "789",
        "123"
    ],
    "bls_public_keys": [
        "347043388985314611088523723672849261459066865147342514766975146031592968981:16865625797537152485129819826310148884042040710059790347821575891945447848787:12298029821069512162285775240688220379514183764628345956323231135392667898379:8",  # noqa
        "347043388985314611088523723672849261459066865147342514766975146031592968982:16865625797537152485129819826310148884042040710059790347821575891945447848788:12298029821069512162285775240688220379514183764628345956323231135392667898380:9"  # noqa
    ],
}

TEST_ORIGINATOR_ADDRESS = '0x0B5e3eBB74eE281A24DDa3B1A4e70692c15EAC34'
TEST_MAINNET_OWNER_ADDRESS = '0x30E1C96277735B03E59B3098204fd04FD0e78a46'

TEST_SCHAIN_NODE_WITH_SCHAINS = [{
    'name': 'test',
    'ip': b'\x01\x02\x03\x04',
    'publicIP': b'\x01\x02\x03\x04',
    'publicKey': '0x0B5e3eBB74eE281A24DDa3B1A4e70692c15EAC34',
    'port': 10000,
    'id': 1,
    'schains': [{'name': 'test_schain'}]
}]
TEST_NODE = {'id': 1, 'name': 'test', 'publicKey': '0x5556', 'port': 10000}


SCHAIN_WITHOUT_ORIGINATOR = {
    'name': 'test_schain',
    'partOfNode': 0,
    'generation': 1,
    'mainnetOwner': TEST_MAINNET_OWNER_ADDRESS,
    'originator': '0x0000000000000000000000000000000000000000',
    'multitransactionMode': True
}

SCHAIN_WITH_ORIGINATOR = {
    'name': 'test_schain',
    'partOfNode': 0,
    'generation': 1,
    'mainnetOwner': TEST_MAINNET_OWNER_ADDRESS,
    'originator': TEST_ORIGINATOR_ADDRESS,
    'multitransactionMode': True
}


@pytest.fixture
def schain_secret_key_file(schain_on_contracts, predeployed_ima):
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
def schain_secret_key_file_default_chain(predeployed_ima):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, 'test_schain')
    Path(schain_dir_path).mkdir(exist_ok=True)
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    try:
        yield
    finally:
        Path(secret_key_path).unlink()
        Path(schain_dir_path).rmdir()


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
        'nodeID', 'nodeName', 'basePort', 'httpRpcPort', 'httpsRpcPort',
        'wsRpcPort', 'wssRpcPort', 'bindIP', 'logLevel', 'logLevelConfig',
        'imaMessageProxySChain', 'imaMessageProxyMainNet',
        'ecdsaKeyName', 'wallets', 'minCacheSize',
        'maxCacheSize', 'collectionQueueSize', 'collectionDuration',
        'transactionQueueSize', 'maxOpenLeveldbFiles', 'info-acceptors', 'imaMonitoringPort',
        'skale-manager', 'syncNode', 'pg-threads', 'pg-threads-limit'
    ]

    check_keys(info, keys)
    assert info['nodeID'] == node_id
    check_node_ports(info)
    assert info['infoHttpRpcPort'] == info['basePort'] + 9
    assert info['ecdsaKeyName'] == ECDSA_KEY_NAME


def check_schain_node_info(node_id, schain_node_info, index):
    check_keys(schain_node_info,
               ['nodeID', 'nodeName', 'basePort', 'httpRpcPort',
                'httpsRpcPort', 'wsRpcPort', 'wssRpcPort', 'publicKey',
                'blsPublicKey0', 'blsPublicKey1', 'blsPublicKey2',
                'blsPublicKey3', 'owner', 'schainIndex', 'ip', 'publicIP'])
    assert schain_node_info['nodeID'] == node_id
    check_node_ports(schain_node_info)
    check_node_bls_keys(schain_node_info, index)


def check_schain_info(node_ids, schain_info):
    check_keys(
        schain_info,
        ['schainID', 'schainName', 'blockAuthor', 'contractStorageLimit',
         'dbStorageLimit', 'snapshotIntervalSec', 'emptyBlockIntervalMs',
         'maxConsensusStorageBytes', 'maxSkaledLeveldbStorageBytes',
         'maxFileStorageBytes', 'maxReservedStorageBytes',
         'nodes', 'revertableFSPatchTimestamp', 'contractStoragePatchTimestamp']
    )
    for index, (nid, schain_node_info) in enumerate(zip(
        node_ids,
        schain_info['nodes']
    )):
        check_schain_node_info(nid, schain_node_info, index)


def check_config(node_id, all_node_ids, config):
    check_keys(
        config,
        ['sealEngine', 'params', 'unddos', 'genesis', 'accounts', 'skaleConfig']
    )
    assert config['params']['skaleDisableChainIdCheck'] is True
    check_node_info(node_id, config['skaleConfig']['nodeInfo'])
    check_schain_info(all_node_ids, config['skaleConfig']['sChain'])


def test_generate_schain_config_with_skale(
    skale,
    schain_on_contracts,
    schain_secret_key_file
):
    schain_name = schain_on_contracts
    node_ids = skale.schains_internal.get_node_ids_for_schain(schain_name)
    current_node_id = node_ids[0]
    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        node_id=current_node_id,
        rotation_data={'rotation_id': 0, 'leaving_node': 1},
        ecdsa_key_name=ECDSA_KEY_NAME,
        generation=0,
        node_options=NodeOptions()
    )
    check_config(current_node_id, node_ids, schain_config.to_dict())


def test_generate_schain_config_gen0(schain_secret_key_file_default_chain, skale_manager_opts):
    schain = {
        'name': 'test_schain',
        'partOfNode': 0,
        'generation': 0,
        'mainnetOwner': '0x30E1C96277735B03E59B3098204fd04FD0e78a46',
        'originator': TEST_ORIGINATOR_ADDRESS,
        'multitransactionMode': True
    }

    node_id, generation, rotation_id = 1, 0, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=schain,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['sChain']['blockAuthor'] == TEST_MAINNET_OWNER_ADDRESS
    assert not config['accounts'].get(TEST_ORIGINATOR_ADDRESS)


def test_generate_schain_config_gen1(schain_secret_key_file_default_chain, skale_manager_opts):
    node_id, generation, rotation_id = 1, 1, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=SCHAIN_WITH_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=True,
        skale_manager_opts=skale_manager_opts
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


def test_generate_schain_config_gen1_pk_owner(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 1, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts
    )
    config = schain_config.to_dict()

    assert not config['accounts'].get(TEST_ORIGINATOR_ADDRESS)
    assert config['accounts'].get(TEST_MAINNET_OWNER_ADDRESS)


def test_generate_schain_config_gen2_schain_id(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 2, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 2755779573749746


def test_generate_schain_config_gen1_schain_id(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 1, 0
    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name='test',
        schains_on_node=[{'name': 'test_schain'}],
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups={},
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 1


def test_generate_schain_config_gen0_schain_id(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 0, 0
    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name='test',
        schains_on_node=[{'name': 'test_schain'}],
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups={},
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts
    )
    config = schain_config.to_dict()
    assert config['skaleConfig']['sChain']['schainID'] == 1


def test_generate_schain_config_with_skale_gen2(
    skale,
    schain_on_contracts,
    schain_secret_key_file
):
    schain_name = schain_on_contracts
    node_ids = skale.schains_internal.get_node_ids_for_schain(schain_name)
    current_node_id = node_ids[0]
    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        node_id=current_node_id,
        rotation_data={'rotation_id': 0, 'leaving_node': 1},
        ecdsa_key_name=ECDSA_KEY_NAME,
        generation=2
    )
    schain_config_dict = schain_config.to_dict()
    check_config(current_node_id, node_ids, schain_config_dict)
    assert schain_config_dict['skaleConfig']['sChain']['schainID'] == get_schain_id(schain_name)


def test_get_schain_originator(predeployed_ima):
    originator = get_schain_originator(SCHAIN_WITHOUT_ORIGINATOR)
    assert originator == TEST_MAINNET_OWNER_ADDRESS

    originator = get_schain_originator(SCHAIN_WITH_ORIGINATOR)
    assert originator == TEST_ORIGINATOR_ADDRESS


def test_generate_sync_node_config(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 1, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts,
        sync_node=True
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo']['syncNode']
    assert config['skaleConfig']['sChain']['dbStorageLimit'] == 1331999539


def test_generate_sync_node_config_archive_catchup(
    schain_secret_key_file_default_chain,
    skale_manager_opts
):
    node_id, generation, rotation_id = 1, 1, 0
    ecdsa_key_name = 'test'
    schains_on_node = [{'name': 'test_schain'}]
    node_groups = {}

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts,
        sync_node=True
    )
    config = schain_config.to_dict()

    assert not config['skaleConfig']['nodeInfo'].get('syncFromCatchup')
    assert not config['skaleConfig']['nodeInfo'].get('archiveMode')

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts,
        sync_node=True,
        archive=False,
        catchup=True
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo'].get('syncFromCatchup')
    assert config['skaleConfig']['nodeInfo'].get('archiveMode') is False

    schain_config = generate_schain_config(
        schain=SCHAIN_WITHOUT_ORIGINATOR,
        node=TEST_NODE,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=TEST_SCHAIN_NODE_WITH_SCHAINS,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=False,
        skale_manager_opts=skale_manager_opts,
        sync_node=False,
        archive=False,
        catchup=True
    )
    config = schain_config.to_dict()

    assert config['skaleConfig']['nodeInfo'].get('syncFromCatchup') is None
    assert config['skaleConfig']['nodeInfo'].get('archiveMode') is None
