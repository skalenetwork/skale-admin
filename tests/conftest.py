import json
import os
import pathlib
import random
import string
import subprocess

import pytest
from skale.utils.contracts_provision.main import (create_nodes, create_schain,
                                                  cleanup_nodes_schains)
from core.schains.checks import SChainChecks
from core.schains.cleaner import remove_schain_container
from core.schains.cleaner import remove_schain_volume
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config
)
from core.node_config import NodeConfig

from core.schains.ima import ImaData

from tests.utils import (
    CONTAINERS_JSON,
    generate_cert,
    get_test_rule_controller,
    init_skale_ima,
    init_web3_skale
)
from tools.configs import META_FILEPATH, SSL_CERTIFICATES_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import CONTAINERS_FILEPATH
from tools.docker_utils import DockerUtils
from web.models.schain import create_tables, SChainRecord, upsert_schain_record


@pytest.fixture
def containers_json():
    with open(CONTAINERS_FILEPATH, 'w') as cf:
        json.dump(CONTAINERS_JSON, cf)
    yield CONTAINERS_FILEPATH
    os.remove(CONTAINERS_FILEPATH)


@pytest.fixture
def skale():
    return init_web3_skale()


@pytest.fixture
def skale_ima():
    return init_skale_ima()


@pytest.fixture
def ssl_folder():
    pathlib.Path(SSL_CERTIFICATES_FILEPATH).mkdir(
        parents=True,
        exist_ok=True
    )
    try:
        yield SSL_CERTIFICATES_FILEPATH
    finally:
        pathlib.Path(SSL_CERTIFICATES_FILEPATH).rmdir()


@pytest.fixture
def cert_key_pair(ssl_folder):
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    generate_cert(cert_path, key_path)
    yield cert_path, key_path
    pathlib.Path(cert_path).unlink(missing_ok=True)
    pathlib.Path(key_path).unlink(missing_ok=True)


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
                "basePort": 10000,
                "httpRpcPort": 10003,
                "httpsRpcPort": 10008,
                "wsRpcPort": 10002,
                "wssRpcPort": 10007,
                "infoHttpRpcPort": 10008,
                "pgHttpRpcPort": 10100,
                "pgHttpsRpcPort": 10110,
                "infoPgHttpRpcPort": 10120,
                "infoPgHttpsRpcPort": 10130,
                "bindIP": "0.0.0.0",
                "ecdsaKeyName": "NEK:518",
                "imaMonitoringPort": 10006
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
                        "infoHttpRpcPort": 10008,
                        "pgHttpRpcPort": 10100,
                        "pgHttpsRpcPort": 10110,
                        "infoPgHttpRpcPort": 10120,
                        "infoPgHttpsRpcPort": 10130,
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
                        "pgHttpRpcPort": 10040,
                        "pgHttpsRpcPort": 10050,
                        "infoPgHttpRpcPort": 10060,
                        "infoPgHttpsRpcPort": 10070,
                        "schainIndex": 1,
                        "ip": "127.0.0.2",
                        "owner": "0x42",
                        "publicIP": "127.0.0.2"
                    }
                ]
            }
        }
    }


SECRET_KEY = {
    "common_public_key": [
        11111111111111111111111111111111111111111111111111111111111111111111111111111,
        1111111111111111111111111111111111111111111111111111111111111111111111111111,
        1111111111111111111111111111111111111111111111111111111111111111111111111111,
        11111111111111111111111111111111111111111111111111111111111111111111111111111
    ],
    "public_key": [
        "1111111111111111111111111111111111111111111111111111111111111111111111111111",
        "1111111111111111111111111111111111111111111111111111111111111111111111111111",
        "1111111111111111111111111111111111111111111111111111111111111111111111111111",
        "11111111111111111111111111111111111111111111111111111111111111111111111111111"
    ],
    "bls_public_keys": [
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111",  # noqa
        "1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111"   # noqa
    ],
    "t": 11,
    "n": 16,
    "key_share_name": "BLS_KEY:SCHAIN_ID:33333333333333333333333333333333333333333333333333333333333333333333333333333:NODE_ID:0:DKG_ID:0"  # noqa
}


@pytest.fixture
def _schain_name():
    """ Generates default schain name """
    return get_random_string()


@pytest.fixture
def schain_config(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
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


@pytest.fixture
def db():
    create_tables()
    yield
    SChainRecord.drop_table()


@pytest.fixture
def schain_db(db, _schain_name, meta_file):
    """ Database with default schain inserted """
    config_version = meta_file['config_stream']
    r = upsert_schain_record(_schain_name)
    r.set_config_version(config_version)
    return _schain_name


@pytest.fixture
def meta_file():
    meta_info = {
        "version": "0.0.0",
        "config_stream": "1.0.0-testnet",
        "docker_lvmpy_stream": "1.1.1"
    }
    with open(META_FILEPATH, 'w') as meta_file:
        json.dump(meta_info, meta_file)
    yield meta_info
    os.remove(META_FILEPATH)


@pytest.fixture
def schain_on_contracts(skale, _schain_name) -> str:
    cleanup_nodes_schains(skale)
    create_nodes(skale)
    create_schain(skale, _schain_name)
    yield _schain_name
    cleanup_nodes_schains(skale)


@pytest.fixture
def dutils():
    return DockerUtils(
        volume_driver='local',
        host='unix://var/run/docker.sock'
    )


@pytest.fixture
def skaled_mock_image(scope='module'):
    dutils = DockerUtils(
        volume_driver='local',
        host='unix://var/run/docker.sock'
    )
    name = 'skaled-mock'
    dutils.client.images.build(
        tag=name,
        rm=True,
        nocache=True,
        path='tests/skaled-mock'
    )
    yield name
    dutils.client.images.remove(name, force=True)


@pytest.fixture
def cleanup_container(schain_config, dutils):
    yield
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    cleanup_schain_container(schain_name, dutils)


def cleanup_schain_container(schain_name: str, dutils: DockerUtils):
    remove_schain_container(schain_name, dutils)
    remove_schain_volume(schain_name, dutils)


@pytest.fixture
def node_config(skale):
    node_config = NodeConfig()
    node_config.id = 0
    return node_config


@pytest.fixture
def schain_checks(schain_config, schain_db, rule_controller, dutils):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    return SChainChecks(
        schain_name,
        node_id,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )


@pytest.fixture
def schain_struct(schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    return {
        'name': schain_name,
        'partOfNode': 0,
        'generation': 0
    }


@pytest.fixture
def ima_data(skale):
    return ImaData(linked=True, chain_id=skale.web3.eth.chainId)


@pytest.fixture
def rule_controller(_schain_name, schain_db, schain_config):
    base_port = get_base_port_from_config(schain_config)
    own_ip = get_own_ip_from_config(schain_config)
    node_ips = get_node_ips_from_config(schain_config)
    return get_test_rule_controller(
        name=_schain_name,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips
    )


@pytest.fixture
def synced_rule_controller(rule_controller):
    rule_controller.sync()
    return rule_controller


@pytest.fixture
def uninited_rule_controller(_schain_name):
    return get_test_rule_controller(name=_schain_name)
