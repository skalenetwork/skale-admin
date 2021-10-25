import json
import os
from pathlib import Path

import pytest

from core.schains.config.generator import generate_schain_config_with_skale
from tools.configs.schains import SCHAINS_DIR_PATH


SCHAIN_ID = 1

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


@pytest.fixture
def schain_secret_key_file(schain_on_contracts):
    schain_name = schain_on_contracts
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    Path(schain_dir_path).mkdir(exist_ok=True)
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    yield
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
    assert info['publicKey'] == '0x513462e7ff260ae614a8a9404419c0521963cffa098b1328239cb3e694fa2f34eb4d170b296029ae47c26df6a2e66fd3e5176651341604cc0b1c3fb337e68800'  # noqa


def check_node_info(node_id, info):
    keys = ['nodeID', 'nodeName', 'basePort', 'httpRpcPort', 'httpsRpcPort',
            'wsRpcPort', 'wssRpcPort', 'bindIP', 'logLevel', 'logLevelConfig',
            'imaMessageProxySChain', 'imaMessageProxyMainNet',
            'rotateAfterBlock', 'ecdsaKeyName', 'wallets', 'minCacheSize',
            'maxCacheSize', 'collectionQueueSize', 'collectionDuration',
            'transactionQueueSize', 'maxOpenLeveldbFiles']
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
        ['schainID', 'schainName', 'schainOwner', 'contractStorageLimit',
         'dbStorageLimit', 'snapshotIntervalSec', 'emptyBlockIntervalMs',
         'maxConsensusStorageBytes', 'maxSkaledLeveldbStorageBytes',
         'maxFileStorageBytes', 'maxReservedStorageBytes',
         'nodes']
    )
    for index, (nid, schain_node_info) in enumerate(zip(
        node_ids,
        schain_info['nodes']
    )):
        check_schain_node_info(nid, schain_node_info, index)


def check_config(node_id, all_node_ids, config):
    check_keys(
        config,
        ['sealEngine', 'params', 'genesis', 'accounts', 'skaleConfig']
    )
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
        rotation_id=0,
        ecdsa_key_name=ECDSA_KEY_NAME
    )
    check_config(current_node_id, node_ids, schain_config.to_dict())
