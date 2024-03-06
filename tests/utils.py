""" SKALE test utilities """

import os
import json
import random
import requests
import string
import time
from contextlib import contextmanager

from mock import Mock, MagicMock

from skale import Skale, SkaleIma
from skale.utils.web3_utils import init_web3
from skale.wallets import Web3Wallet
from web3 import Web3

from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.schains.config.file_manager import ConfigFileManager
from core.schains.firewall.types import IHostFirewallController, IpRange
from core.schains.firewall import SChainFirewallManager, SChainRuleController
from core.schains.runner import (
    get_image_name,
    run_schain_container,
    run_ima_container,
    get_container_info
)

from tools.docker_utils import DockerUtils
from tools.helper import run_cmd
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.configs.web3 import ABI_FILEPATH

from web.models.schain import upsert_schain_record


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
IMA_ABI_FILEPATH = os.getenv('IMA_ABI_FILEPATH') or os.path.join(
    DIR_PATH, os.pardir, 'helper-scripts', 'contracts_data', 'ima.json')


ETH_AMOUNT_PER_NODE = 1
CONFIG_STREAM = "1.0.0-testnet"


ALLOWED_RANGES = [
    IpRange('1.1.1.1', '2.2.2.2'),
    IpRange('3.3.3.3', '4.4.4.4')
]


class FailedAPICall(Exception):
    pass


def generate_random_ip():
    return '.'.join('%s' % random.randint(0, 255) for i in range(4))


def generate_random_name(len=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=len))


def generate_random_port():
    return random.randint(0, 60000)


def generate_random_node_data():
    return generate_random_ip(), generate_random_ip(), generate_random_port(), \
        generate_random_name()


def generate_cert(cert_path, key_path):
    return run_cmd([
        'openssl', 'req',
        '-newkey', 'rsa:4096',
        '-x509',
        '-sha256',
        '-days', '365',
        '-nodes',
        '-subj', '/',
        '-out', cert_path,
        '-keyout', key_path
    ])


def generate_random_schain_data():
    lifetime_seconds = 3600  # 1 hour
    type_of_nodes = 1
    return type_of_nodes, lifetime_seconds, generate_random_name()


def get_bp_data(bp, request, params=None, full_data=False, **kwargs):
    data = bp.get(request, query_string=params, **kwargs).data
    if full_data:
        return data

    return json.loads(data.decode('utf-8'))


def post_bp_data(bp, request, params=None, full_response=False, **kwargs):
    data = bp.post(request, json=params).data
    if full_response:
        return data
    return json.loads(data.decode('utf-8'))


def get_schain_contracts_data(schain_name):
    """ Schain data mock in case if schain on contracts is not required """
    return {
        'name': schain_name,
        'mainnetOwner': '0x1213123091a230923123213123',
        'indexInOwnerList': 0,
        'partOfNode': 0,
        'lifetime': 3600,
        'startDate': 1575448438,
        'deposit': 1000000000000000000,
        'index': 0,
        'active': True
    }


def run_simple_schain_container(schain_data: dict, dutils: DockerUtils):
    run_schain_container(schain_data, dutils=dutils)


def run_simple_schain_container_in_sync_mode(schain_data: dict,
                                             dutils: DockerUtils):
    public_key = "1:1:1:1"
    timestamp = int(time.time())
    run_schain_container(schain_data, public_key, timestamp, dutils=dutils)


def run_simple_ima_container(schain: dict, dutils: DockerUtils):
    image = get_image_name(image_type=IMA_CONTAINER)
    run_ima_container(schain, mainnet_chain_id=1, image=image, dutils=dutils)


def init_web3_skale() -> Skale:
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return init_skale_from_wallet(wallet)


def init_skale_from_wallet(wallet) -> Skale:
    return Skale(ENDPOINT, ABI_FILEPATH, wallet)


def init_skale_ima():
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return SkaleIma(ENDPOINT, IMA_ABI_FILEPATH, wallet)


def init_web3_wallet() -> Web3Wallet:
    web3 = init_web3(ENDPOINT)
    return Web3Wallet(ETH_PRIVATE_KEY, web3)


def response_mock(status_code=0, json_data=None, cookies=None,
                  headers=None, raw=None):
    result = MagicMock()
    result.status_code = status_code
    result.json = MagicMock(return_value=json_data)
    result.cookies = cookies
    result.headers = headers
    result.raw = raw
    return result


def request_mock(response_mock):
    return Mock(return_value=response_mock)


def alter_schain_config(schain_name: str, public_key: str) -> None:
    """
    Fix config to make skaled work with a single node (mine blocks, etc)
    """
    cfm = ConfigFileManager(schain_name)
    config = cfm.skaled_config
    node = config['skaleConfig']['sChain']['nodes'][0]
    node['publicKey'] = public_key
    config['skaleConfig']['sChain']['nodes'] = [node]
    cfm.save_skaled_config(config)


class HostTestFirewallController(IHostFirewallController):
    def __init__(self):
        self._rules = set()

    def add_rule(self, srule):
        self._rules.add(srule)

    def remove_rule(self, srule):
        if self.has_rule(srule):
            self._rules.remove(srule)

    @property
    def rules(self):
        return iter(self._rules)

    def has_rule(self, srule):
        return srule in self._rules


class SChainTestFirewallManager(SChainFirewallManager):
    def create_host_controller(self):
        return HostTestFirewallController()


class SChainTestRuleController(SChainRuleController):
    def create_firewall_manager(self):
        return SChainTestFirewallManager(
            self.name,
            self.base_port,
            self.base_port + self.ports_per_schain
        )


def get_test_rule_controller(
    name,
    base_port=None,
    own_ip=None,
    node_ips=[],
    sync_agent_ranges=[],
    synced=False
):
    rc = SChainTestRuleController(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )
    if synced:
        rc.sync()
    return rc


@contextmanager
def no_schain_artifacts(schain_name, dutils):
    try:
        yield
    finally:
        remove_schain_container(schain_name, dutils=dutils)
        time.sleep(10)
        remove_schain_volume(schain_name, dutils=dutils)
        remove_config_dir(schain_name)


def run_custom_schain_container(dutils, schain_name, entrypoint):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_name)
    return dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint=entrypoint
    )


def upsert_schain_record_with_config(name, version=None):
    version = version or CONFIG_STREAM
    r = upsert_schain_record(name)
    r.set_config_version(version)
    return r


def set_interval_mining(w3: Web3, interval: int) -> None:
    endpoint = w3.provider.endpoint_uri
    data = {'jsonrpc': '2.0', 'method': 'evm_setIntervalMining', 'params': [interval], "id": 101}
    r = requests.post(endpoint, json=data)
    assert r.status_code == 200 and 'error' not in r.json()


def set_automine(w3: Web3, value: bool) -> None:
    endpoint = w3.provider.endpoint_uri
    data = {'jsonrpc': '2.0', 'method': 'evm_setAutomine', 'params': [value], "id": 102}
    r = requests.post(endpoint, json=data)
    assert r.status_code == 200 and 'error' not in r.json()


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
            "blockReward": "0x4563918244F40000",
            "skaleDisableChainIdCheck": True
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
                "basePort": 10000,
                "httpRpcPort": 10003,
                "httpsRpcPort": 10008,
                "wsRpcPort": 10002,
                "wssRpcPort": 10007,
                "infoHttpRpcPort": 10008,
                "bindIP": "0.0.0.0",
                "ecdsaKeyName": "NEK:518",
                "imaMonitoringPort": 10006,
                "wallets": {
                    "ima": {
                        "keyShareName": "bls_key:schain_id:33333333333333333333333333333333333333333333333333333333333333333333333333333:node_id:0:dkg_id:0",  # noqa
                        "t": 11,
                        "n": 16,
                        "certfile": "sgx.crt",
                        "keyfile": "sgx.key",
                        "commonBlsPublicKey0": "11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "commonBlsPublicKey1": "1111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "commonBlsPublicKey2": "1111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "commonBlsPublicKey3": "11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "blsPublicKey0": "1111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "blsPublicKey1": "1111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "blsPublicKey2": "1111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
                        "blsPublicKey3": "11111111111111111111111111111111111111111111111111111111111111111111111111111"  # noqa
                    }
                },
            },
            "sChain": {
                "schainID": 1,
                "schainName": schain_name,
                "schainOwner": "0x3483A10F7d6fDeE0b0C1E9ad39cbCE13BD094b12",


                "nodeGroups": {
                    "1": {
                        "rotation": None,
                        "nodes": {
                            "2": [
                                0,
                                2,
                                "0xc21d242070e84fe5f8e80f14b8867856b714cf7d1984eaa9eb3f83c2a0a0e291b9b05754d071fbe89a91d4811b9b182d350f706dea6e91205905b86b4764ef9a"  # noqa
                            ],
                            "5": [
                                1,
                                5,
                                "0xc37b6db727683379d305a4e38532ddeb58c014ebb151662635839edf3f20042bcdaa8e4b1938e8304512c730671aedf310da76315e329be0814709279a45222a"  # noqa
                            ],
                            "4": [
                                2,
                                4,
                                "0x8b335f65ecf0845d93bc65a340cc2f4b8c49896f5023ecdff7db6f04bc39f9044239f541702ca7ad98c97aa6a7807aa7c41e394262cca0a32847e3c7c187baf5"  # noqa
                            ],
                            "3": [
                                3,
                                3,
                                "0xf3496966c7fd4a82967d32809267abec49bf5c4cc6d88737cee9b1a436366324d4847127a1220575f4ea6a7661723cd5861c9f8de221405b260511b998a0bbc8"  # noqa
                            ]
                        },
                        "finish_ts": None,
                        "bls_public_key": {
                            "blsPublicKey0": "8609115311055863404517113391175862520685049234001839865086978176708009850942",  # noqa
                            "blsPublicKey1": "12596903066793884087763787291339131389612748572700005223043813683790087081",  # noqa
                            "blsPublicKey2": "20949401227653007081557504259342598891084201308661070577835940778932311075846",  # noqa
                            "blsPublicKey3": "5476329286206272760147989277520100256618500160343291262709092037265666120930"  # noqa
                        }
                    },
                    "0": {
                        "rotation": {
                            "leaving_node_id": 1,
                            "new_node_id": 5
                        },
                        "nodes": {
                            "2": [
                                0,
                                2,
                                "0xc21d242070e84fe5f8e80f14b8867856b714cf7d1984eaa9eb3f83c2a0a0e291b9b05754d071fbe89a91d4811b9b182d350f706dea6e91205905b86b4764ef9a"  # noqa
                            ],
                            "4": [
                                2,
                                4,
                                "0x8b335f65ecf0845d93bc65a340cc2f4b8c49896f5023ecdff7db6f04bc39f9044239f541702ca7ad98c97aa6a7807aa7c41e394262cca0a32847e3c7c187baf5"  # noqa
                            ],
                            "3": [
                                3,
                                3,
                                "0xf3496966c7fd4a82967d32809267abec49bf5c4cc6d88737cee9b1a436366324d4847127a1220575f4ea6a7661723cd5861c9f8de221405b260511b998a0bbc8"  # noqa
                            ],
                            "1": [
                                1,
                                1,
                                "0x1a857aa4a982ba242c2386febf1eb72dcd1f9669b4237a17878eb836086618af6cda473afa2dfb37c0d2786887397d39bec9601234d933d4384fe38a39b399df"  # noqa
                            ]
                        },
                        "finish_ts": 1687180291,
                        "bls_public_key": {
                            "blsPublicKey0": "12452613198400495171048259986807077228209876295033433688114313813034253740478",  # noqa
                            "blsPublicKey1": "10490413552821776191285904316985887024952448646239144269897585941191848882433",  # noqa
                            "blsPublicKey2": "892041650350974543318836112385472656918171041007469041098688469382831828315",  # noqa
                            "blsPublicKey3": "14699659615059580586774988732364564692366017113631037780839594032948908579205"  # noqa
                        }
                    }
                },
                "nodes": [
                    {
                        "nodeID": 0,
                        "nodeName": "test-node0",
                        "basePort": 10000,
                        "httpRpcPort": 100003,
                        "httpsRpcPort": 10008,
                        "wsRpcPort": 10002,
                        "wssRpcPort": 10007,
                        "infoHttpRpcPort": 10008,
                        "schainIndex": 1,
                        "ip": "127.0.0.1",
                        "owner": "0x41",
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
                        "infoHttpRpcPort": 10019,
                        "schainIndex": 1,
                        "ip": "127.0.0.2",
                        "owner": "0x42",
                        "publicIP": "127.0.0.2"
                    }
                ]
            }
        }
    }
