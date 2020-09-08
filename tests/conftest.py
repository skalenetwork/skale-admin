import json
import os
from pathlib import Path

import pytest
from skale import Skale
from skale.wallets import Web3Wallet
from skale.utils.web3_utils import init_web3

from tools.configs.schains import SCHAINS_DIR_PATH

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.path.join(DIR_PATH, 'test_abi.json')


@pytest.fixture
def skale():
    return init_skale()


def init_skale():
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)


SCHAIN_NAME = 'test'

SCHAIN_CONFIG = {
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
              "nodeID": 1,
              "nodeName": "test-node",
              "basePort": 2231,
              "httpRpcPort": 2234,
              "httpsRpcPort": 10002,
              "wsRpcPort": 10003,
              "wssRpcPort": 10008,
              "bindIP": "0.0.0.0"
          },
          "sChain": {
              "schainID": 1,
              "schainName": "test-chain",
              "schainOwner": "0x3483A10F7d6fDeE0b0C1E9ad39cbCE13BD094b12",
              "nodes": [
                  {
                      "nodeID": 1,
                      "nodeName": "test-node",
                      "basePort": 2231,
                      "httpRpcPort": 2234,
                      "httpsRpcPort": 10002,
                      "wsRpcPort": 10003,
                      "wssRpcPort": 10008,
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
def schain_dir():
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, SCHAIN_NAME)
    Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    config_path = os.path.join(schain_dir_path,
                               f'schain_{SCHAIN_NAME}.json')
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    with open(config_path, 'w') as config_file:
        json.dump(SCHAIN_CONFIG, config_file)
    with open(secret_key_path, 'w') as key_file:
        json.dump(SECRET_KEY, key_file)
    yield
    Path(config_path).unlink()
    Path(secret_key_path).unlink()
    Path(schain_dir_path).rmdir()
