import os
import json
import random
import string
import subprocess
import shutil
from pathlib import Path

import pytest

from skale import Skale
from skale.wallets import Web3Wallet
from skale.utils.contracts_provision.main import (create_nodes, create_schain,
                                                  cleanup_nodes_schains)
from skale.utils.web3_utils import init_web3

from tools.configs.schains import SCHAINS_DIR_PATH

from web.models.schain import create_tables, SChainRecord, upsert_schain_record

ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH')


@pytest.fixture
def skale():
    return init_skale()


def init_skale():
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)


def get_random_string(length=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def generate_schain_config(schain_name):
    return {
        "sealEngine": "Ethash",
        "params": {
            "accountStartNonce": "0x00",
            "homesteadForkBlock": "0x0",
            "daoHardforkBlock": "0x0",
            "EIP150ForkBlock": "0x00",
            "EIP158ForkBlock": "0x00",
            "byzantiumForkBlock": "0x0",
            "constantinopleForkBlock": "0x0",
            "networkID": "12313219",
            "chainID": "0x01",
            "maximumExtraDataSize": "0x20",
            "tieBreakingGas": False,
            "minGasLimit": "0xFFFFFFF",
            "maxGasLimit": "7fffffffffffffff",
            "gasLimitBoundDivisor": "0x0400",
            "minimumDifficulty": "0x020000",
            "difficultyBoundDivisor": "0x0800",
            "durationLimit": "0x0d",
            "blockReward": "0x4563918244F40000"
        },
        "genesis": {
            "nonce": "0x0000000000000042",
            "difficulty": "0x020000",
            "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "author": "0x0000000000000000000000000000000000000000",
            "timestamp": "0x00",
            "parentHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "extraData": "0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa",
            "gasLimit": "0xFFFFFFF"
        },
        "accounts": {
        },
        "skaleConfig": {
            "nodeInfo": {
                "nodeID": 0,
                "nodeName": "test-node1",
                "basePort": 2231,
                "httpRpcPort": 2234,
                "httpsRpcPort": 10002,
                "wsRpcPort": 10003,
                "wssRpcPort": 10008,
                "bindIP": "0.0.0.0"
            },
            "sChain": {
                "schainID": 1,
                "schainName": schain_name,
                "schainOwner": "0x3483A10F7d6fDeE0b0C1E9ad39cbCE13BD094b12",
                "nodes": [
                    {
                        "nodeID": 0,
                        "nodeName": "test-node0",
                        "basePort": 10000,
                        "httpRpcPort": 100003,
                        "httpsRpcPort": 10008,
                        "wsRpcPort": 10002,
                        "wssRpcPort": 10007,
                        "schainIndex": 1,
                        "ip": "127.0.0.1",
                        "publicIP": "127.0.0.1"
                    },
                    {
                        "nodeID": 1,
                        "nodeName": "test-node1",
                        "basePort": 10010,
                        "httpRpcPort": 10013,
                        "httpsRpcPort": 10017,
                        "wsRpcPort": 10012,
                        "wssRpcPort": 10018,
                        "schainIndex": 1,
                        "ip": "127.0.0.1",
                        "publicIP": "127.0.0.1"
                    }
                ]
            }
        }
    }


SECRET_KEY = {
    "key_share_name": "BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0",
    "t": 3,
    "n": 4,
    "common_public_key": [123, 456, 789, 123],
    "public_key": ["123", "456", "789", "123"]
}


@pytest.fixture
def _schain_name():
    """ Generates default schain name """
    return 'schain_' + get_random_string()


@pytest.fixture
def schain_config(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    config_path = os.path.join(schain_dir_path,
                               f'schain_{_schain_name}.json')
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    schain_config = generate_schain_config(_schain_name)
    with open(config_path, 'w') as config_file:
        json.dump(schain_config, config_file)
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    yield schain_config
    # fix permission denied after schain container running
    subprocess.run(['rm', '-rf', schain_dir_path])
    shutil.rmtree(schain_dir_path, ignore_errors=True)


@pytest.fixture
def db():
    create_tables()
    upsert_schain_record
    yield
    SChainRecord.drop_table()


@pytest.fixture
def schain_db(db, _schain_name):
    """ Database with default schain inserted """
    upsert_schain_record(_schain_name)
    return _schain_name


@pytest.fixture
def schain_on_contracts(skale, _schain_name) -> str:
    cleanup_nodes_schains(skale)
    create_nodes(skale)
    create_schain(skale, _schain_name)
    yield _schain_name
    cleanup_nodes_schains(skale)
