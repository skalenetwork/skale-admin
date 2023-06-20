import json
import os
import pathlib
import random
import shutil
import string
import subprocess
from pathlib import Path

import docker
import pytest


from skale import SkaleManager
from skale.wallets import Web3Wallet
from skale.utils.account_tools import generate_account, send_eth
from skale.utils.contracts_provision.fake_multisig_contract import (
    deploy_fake_multisig_contract
)
from skale.utils.contracts_provision.main import (
    add_test_permissions,
    add_test2_schain_type,
    cleanup_nodes,
    cleanup_nodes_schains,
    create_nodes,
    create_schain,
    link_nodes_to_validator,
    setup_validator
)
from skale.utils.web3_utils import init_web3

from core.ima.schain import update_predeployed_ima
from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config
)
from core.schains.config.directory import schain_config_dir, skaled_status_filepath
from core.schains.cleaner import remove_schain_container, remove_schain_volume
from core.schains.ima import ImaData
from core.schains.skaled_status import init_skaled_status, SkaledStatus
from core.schains.config.skale_manager_opts import SkaleManagerOpts

from tools.configs import META_FILEPATH, SSL_CERTIFICATES_FILEPATH
from tools.configs.containers import CONTAINERS_FILEPATH
from tools.configs.ima import SCHAIN_IMA_ABI_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.web3 import ABI_FILEPATH
from tools.docker_utils import DockerUtils
from tools.helper import write_json

from web.models.schain import create_tables, SChainRecord

from tests.utils import (
    CONFIG_STREAM,
    ENDPOINT,
    ETH_AMOUNT_PER_NODE,
    ETH_PRIVATE_KEY,
    generate_cert,
    get_test_rule_controller,
    init_skale_from_wallet,
    init_skale_ima,
    upsert_schain_record_with_config
)

NUMBER_OF_NODES = 2


@pytest.fixture(scope='session')
def images():
    dclient = docker.from_env()
    cinfo = {}
    with open(CONTAINERS_FILEPATH, 'r') as cf:
        json.load(cinfo, cf)
    schain_image = '{}/{}'.format(
        cinfo['schain']['name'],
        cinfo['schain']['version']
    )
    ima_image = '{}/{}'.format(
        cinfo['ima']['name'],
        cinfo['ima']['version']
    )
    dclient.images.pull(schain_image)
    dclient.images.pull(ima_image)


@pytest.fixture(scope='session')
def predeployed_ima():
    try:
        update_predeployed_ima()
        yield
    finally:
        os.remove(SCHAIN_IMA_ABI_FILEPATH)


@pytest.fixture(scope='session')
def web3():
    """ Returns a SKALE Manager instance with provider from config """
    w3 = init_web3(ENDPOINT)
    return w3


@pytest.fixture(scope='session')
def skale(web3):
    """ Returns a SKALE Manager instance with provider from config """
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    skale_obj = init_skale_from_wallet(wallet)
    add_test_permissions(skale_obj)
    add_test2_schain_type(skale_obj)
    if skale_obj.constants_holder.get_launch_timestamp() != 0:
        skale_obj.constants_holder.set_launch_timestamp(0)
    deploy_fake_multisig_contract(skale_obj.web3, skale_obj.wallet)
    return skale_obj


@pytest.fixture(scope='session')
def validator(skale):
    return setup_validator(skale)


@pytest.fixture
def node_wallets(skale):
    wallets = []
    for i in range(NUMBER_OF_NODES):
        acc = generate_account(skale.web3)
        pk = acc['private_key']
        wallet = Web3Wallet(pk, skale.web3)
        send_eth(
            web3=skale.web3,
            wallet=skale.wallet,
            receiver_address=wallet.address,
            amount=ETH_AMOUNT_PER_NODE
        )
        wallets.append(wallet)
    return wallets


@pytest.fixture
def node_skales(skale, node_wallets):
    return [
        SkaleManager(ENDPOINT, ABI_FILEPATH, wallet)
        for wallet in node_wallets
    ]


@pytest.fixture
def nodes(skale, node_skales, validator):
    link_nodes_to_validator(skale, validator, node_skales)
    ids = create_nodes(node_skales)
    try:
        yield ids
    finally:
        cleanup_nodes(skale, ids)


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
    try:
        yield cert_path, key_path
    finally:
        pathlib.Path(cert_path).unlink(missing_ok=True)
        pathlib.Path(key_path).unlink(missing_ok=True)


def get_random_string(length=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def get_skaled_status_dict(
    snapshot_downloader=False,
    exit_time_reached=False,
    clear_data_dir=False,
    start_from_snapshot=False,
    start_again=False
):
    return {
        "subsystemRunning": {
            "SnapshotDownloader": snapshot_downloader,
            "Blockchain": False,
            "Rpc": False
        },
        "exitState": {
            "ClearDataDir": clear_data_dir,
            "StartAgain": start_again,
            "StartFromSnapshot": start_from_snapshot,
            "ExitTimeReached": exit_time_reached
        }
    }


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
                "imaMonitoringPort": 10006
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
def secret_key(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    secret_key_path = os.path.join(schain_dir_path, 'secret_key_0.json')
    try:
        pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
        with open(secret_key_path, 'w') as key_file:
            json.dump(SECRET_KEY, key_file)
        yield SECRET_KEY
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def schain_config(_schain_name, secret_key, predeployed_ima):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    config_path = os.path.join(schain_dir_path,
                               f'schain_{_schain_name}.json')
    try:
        pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
        schain_config = generate_schain_config(_schain_name)
        with open(config_path, 'w') as config_file:
            json.dump(schain_config, config_file)
        yield schain_config
    finally:
        rm_schain_dir(_schain_name)


def generate_schain_skaled_status_file(_schain_name, **kwargs):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    status_filepath = skaled_status_filepath(_schain_name)
    write_json(status_filepath, get_skaled_status_dict(**kwargs))


def rm_schain_dir(schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    # fix permission denied after schain container running
    subprocess.run(['rm', '-rf', schain_dir_path])


@pytest.fixture
def skaled_status(_schain_name):
    generate_schain_skaled_status_file(_schain_name)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_downloading_snapshot(_schain_name):
    generate_schain_skaled_status_file(_schain_name, snapshot_downloader=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_exit_time_reached(_schain_name):
    generate_schain_skaled_status_file(_schain_name, exit_time_reached=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_repair(_schain_name):
    generate_schain_skaled_status_file(_schain_name, clear_data_dir=True, start_from_snapshot=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_reload(_schain_name):
    generate_schain_skaled_status_file(_schain_name, start_again=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_broken_file(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    status_filepath = skaled_status_filepath(_schain_name)
    with open(status_filepath, "w") as text_file:
        text_file.write('abcd')
    try:
        yield SkaledStatus(status_filepath)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def db():
    create_tables()
    try:
        yield
    finally:
        SChainRecord.drop_table()


@pytest.fixture
def schain_db(db, _schain_name, meta_file):
    """ Database with default schain inserted """
    upsert_schain_record_with_config(_schain_name)
    return _schain_name


@pytest.fixture
def meta_file():
    meta_info = {
        "version": "0.0.0",
        "config_stream": CONFIG_STREAM,
        "docker_lvmpy_stream": "1.1.1"
    }
    with open(META_FILEPATH, 'w') as meta_file:
        json.dump(meta_info, meta_file)
    try:
        yield meta_info
    finally:
        os.remove(META_FILEPATH)


@pytest.fixture
def schain_on_contracts(skale, nodes, _schain_name) -> str:
    try:
        yield create_schain(
            skale,
            schain_type=1,  # test2 should have 1 index
            schain_name=_schain_name
        )
    finally:
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
def cleanup_schain_dirs_before():
    shutil.rmtree(SCHAINS_DIR_PATH)
    pathlib.Path(SCHAINS_DIR_PATH).mkdir(parents=True, exist_ok=True)
    return


@pytest.fixture
def cleanup_schain_containers(dutils):
    try:
        yield
    finally:
        containers = dutils.get_all_schain_containers(all=True)
        for container in containers:
            dutils.safe_rm(container.name, force=True)


@pytest.fixture
def cleanup_container(schain_config, dutils):
    try:
        yield
    finally:
        schain_name = schain_config['skaleConfig']['sChain']['schainName']
        cleanup_schain_container(schain_name, dutils)


def cleanup_schain_container(schain_name: str, dutils: DockerUtils):
    remove_schain_container(schain_name, dutils)
    remove_schain_volume(schain_name, dutils)


@pytest.fixture
def node_config(skale, nodes):
    node_config = NodeConfig()
    node_config.id = nodes[0]
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
        stream_version=CONFIG_STREAM,
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
    return ImaData(linked=True, chain_id=skale.web3.eth.chain_id)


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


@pytest.fixture
def skale_manager_opts():
    return SkaleManagerOpts(
        schains_internal_address='0x1656',
        nodes_address='0x7742'
    )


@pytest.fixture
def new_upstream(schain_db):
    name = schain_db
    config_dir = schain_config_dir(name)
    upath = os.path.join(f'schain_{name}_2_2_1_16_1687248983')
    try:
        Path(upath).touch()
        yield upath
    finally:
        shutil.rmtree(config_dir)
