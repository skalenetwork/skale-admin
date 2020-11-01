import json
import os
from pathlib import Path

import pytest

from core.schains.config.generator import (generate_schain_config,
                                           generate_schain_config_with_skale)
from tools.configs.schains import SCHAINS_DIR_PATH


SCHAIN_NODES_WITH_SCHAINS = [{'name': 'test_node_2', 'ip': b'L\xea\xbb\xc9', 'publicIP': b'\xb6w\x01\xfe', 'port': 26155, 'start_block': 236, 'last_reward_date': 1599240149, 'finish_time': 0, 'status': 0, 'validator_id': 1, 'publicKey': '0xf925c203a30ec6cad5a263db3efab7ed4c1fd74c8688167e10a5a22e15ab5018d8553df0ac54ea105a3d21845e5660bc3d4e7c82e7af1daa3baad393b1521467', 'id': 1, 'schains': [{'name': 'test', 'owner': '0x5112cE768917E907191557D7E9521c2590Cdd3A0', 'indexInOwnerList': 0, 'partOfNode': 0, 'lifetime': 3600, 'startDate': 1599240155, 'startBlock': 240, 'deposit': 1000000000000000000, 'index': 0, 'chainId': '0x9ca5dee9297f2', 'active': True}], 'bls_public_key': '0:0:1:0'}, {'name': 'test_node', 'ip': b'\xbc\xbed\xb3', 'publicIP': b'\xcd\xa1\xf4g', 'port': 43118, 'start_block': 232, 'last_reward_date': 1599240145, 'finish_time': 0, 'status': 0, 'validator_id': 1, 'publicKey': '0xf925c203a30ec6cad5a263db3efab7ed4c1fd74c8688167e10a5a22e15ab5018d8553df0ac54ea105a3d21845e5660bc3d4e7c82e7af1daa3baad393b1521467', 'id': 0, 'schains': [{'name': 'test', 'owner': '0x5112cE768917E907191557D7E9521c2590Cdd3A0', 'indexInOwnerList': 0, 'partOfNode': 0, 'lifetime': 3600, 'startDate': 1599240155, 'startBlock': 240, 'deposit': 1000000000000000000, 'index': 0, 'chainId': '0x9ca5dee9297f2', 'active': True}], 'bls_public_key': '0:0:1:0'}]  # noqa
SCHAIN = {
    'name': 'test_schain',
    'owner': '0x5112cE768917E907191557D7E9521c2590Cdd3A0',
    'partOfNode': 32
}
SCHAIN_ID = 1
SCHAIN_NODES_OWNERS = [
    '0x278Af5dD8523e54d0Ce37e27b3cbcc6A3368Ddeb',
    '0x5112cE768917E907191557D7E9521c2590Cdd3A0'
]
SCHAINS_ON_NODE = [
    {
        'name': 'aaa'
    },
    {
        'name': 'test'
    }
]

NODE_ID = 1
NODE = {
    'name': 'test',
    'port': 10000
}

ECDSA_KEY_NAME = 'TEST:KEY:NAME'
ROTATION_ID = 0
COMPLEXITY_NUMBER = 1

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
    ]
}


@pytest.fixture
def schain_secret_key_file():
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, SCHAIN['name'])
    Path(schain_dir_path).mkdir()
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(secret_key_path, 'w') as key_file:
        json.dump(key_file, key_file)
    yield
    Path(secret_key_path).unlink()
    Path(schain_dir_path).rmdir()


def test_generate_schain_config(schain_secret_key_file):
    schain_config = generate_schain_config(
        schain=SCHAIN,
        schain_id=SCHAIN_ID,
        node_id=NODE_ID,
        node=NODE,
        ecdsa_key_name=ECDSA_KEY_NAME,
        schains_on_node=SCHAINS_ON_NODE,
        rotation_id=ROTATION_ID,
        schain_nodes_with_schains=SCHAIN_NODES_WITH_SCHAINS,
        complexity_number=COMPLEXITY_NUMBER
    )
    print(json.dumps(schain_config.to_dict(), indent=2))
    assert False


def test_generate_schain_config_with_skale(skale, schain_secret_key_file):
    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=SCHAIN['name'],
        node_id=NODE_ID,
        rotation_id=ROTATION_ID,
        ecdsa_key_name=ECDSA_KEY_NAME
    )
    print(json.dumps(schain_config.to_dict(), indent=2))
    assert False
