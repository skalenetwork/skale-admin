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
import yaml


from skale import SkaleManager
from skale.wallets import Web3Wallet
from skale.utils.account_tools import generate_account, send_eth
from skale.utils.contracts_provision.fake_multisig_contract import (
    deploy_fake_multisig_contract
)
from skale.utils.contracts_provision.main import (
    add_test_permissions,
    add_test2_schain_type,
    add_test4_schain_type,
    cleanup_nodes,
    cleanup_nodes_schains,
    create_nodes,
    create_schain,
    link_nodes_to_validator,
    setup_validator
)
from skale.utils.web3_utils import init_web3

from core.ima.schain import update_predeployed_ima
from core.node import get_current_nodes
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
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.skaled_status import init_skaled_status, SkaledStatus
from core.schains.config.skale_manager_opts import SkaleManagerOpts

from tools.configs import (
    CONFIG_FOLDER,
    ENV_TYPE,
    META_FILEPATH,
    SSL_CERTIFICATES_FILEPATH,
    STATIC_GROUPS_FOLDER
)
from tools.configs.containers import CONTAINERS_FILEPATH
from tools.configs.ima import SCHAIN_IMA_ABI_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.web3 import ABI_FILEPATH
from tools.docker_utils import DockerUtils
from tools.helper import write_json

from web.models.schain import create_tables, SChainRecord

from tests.utils import (
    ALLOWED_RANGES,
    CONFIG_STREAM,
    ENDPOINT,
    ETH_AMOUNT_PER_NODE,
    ETH_PRIVATE_KEY,
    STATIC_NODE_GROUPS,
    generate_cert,
    generate_schain_config,
    get_test_rule_controller,
    IMA_MIGRATION_TS,
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
    add_test4_schain_type(skale_obj)
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
    cleanup_nodes(skale, skale.nodes.get_active_node_ids())
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
def secret_keys(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    secret_key_path_0 = os.path.join(schain_dir_path, 'secret_key_0.json')
    secret_key_path_1 = os.path.join(schain_dir_path, 'secret_key_1.json')
    try:
        pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
        with open(secret_key_path_0, 'w') as key_file:
            json.dump(SECRET_KEY, key_file)
        with open(secret_key_path_1, 'w') as key_file:
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
    generate_schain_skaled_status_file(
        _schain_name, clear_data_dir=True, start_from_snapshot=True)
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
def schain_on_contracts(skale, nodes, _schain_name):
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
    shutil.rmtree(SCHAINS_DIR_PATH, ignore_errors=True)
    pathlib.Path(SCHAINS_DIR_PATH).mkdir(parents=True, exist_ok=True)
    return


@pytest.fixture
def clean_docker(dutils, cleanup_schain_containers, cleanup_ima_containers):
    pass


@pytest.fixture
def cleanup_schain_containers(dutils):
    try:
        yield
    finally:
        containers = dutils.get_all_schain_containers(all=True)
        for container in containers:
            dutils.safe_rm(container.name, force=True)
            dutils.safe_rm(container.name.replace('schain', 'ima'), force=True)


@pytest.fixture
def cleanup_ima_containers(dutils):
    try:
        yield
    finally:
        containers = dutils.get_all_ima_containers(all=True)
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
def schain_checks(schain_config, schain_db, current_nodes, rule_controller, estate, dutils):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    return SChainChecks(
        schain_name,
        node_id,
        schain_record=schain_record,
        rule_controller=rule_controller,
        stream_version=CONFIG_STREAM,
        current_nodes=current_nodes,
        estate=estate,
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
        shutil.rmtree(config_dir, ignore_errors=True)


@pytest.fixture
def estate(skale):
    return ExternalState(
        ima_linked=True,
        chain_id=skale.web3.eth.chain_id,
        ranges=ALLOWED_RANGES
    )


@pytest.fixture
def econfig(schain_db, estate):
    name = schain_db
    ec = ExternalConfig(name)
    ec.update(estate)
    return ec


@pytest.fixture
def current_nodes(skale, schain_db, schain_on_contracts):
    name = schain_db
    return get_current_nodes(skale, name)


@pytest.fixture
def upstreams(schain_db, schain_config):
    name = schain_db
    config_folder = schain_config_dir(name)
    files = [
        f'schain_{name}_10_1687183338.json',
        f'schain_{name}_9_1687183335.json',
        f'schain_{name}_11_1687183336.json',
        f'schain_{name}_11_1687183337.json',
        f'schain_{name}_11_1687183339.json'
    ]
    try:
        for fname in files:
            fpath = os.path.join(config_folder, fname)
            with open(fpath, 'w') as f:
                json.dump(schain_config, f)
        yield files
    finally:
        shutil.rmtree(config_folder, ignore_errors=True)


@pytest.fixture
def ima_migration_schedule(schain_db):
    name = schain_db
    try:
        migration_schedule_path = os.path.join(CONFIG_FOLDER, 'ima_migration_schedule.yaml')
        with open(migration_schedule_path, 'w') as migration_schedule_file:
            yaml.dump({ENV_TYPE: {name: IMA_MIGRATION_TS}}, migration_schedule_file)
        yield migration_schedule_path
    finally:
        os.remove(migration_schedule_path)


@pytest.fixture
def static_groups_for_schain(_schain_name):
    parent_folder = os.path.join(STATIC_GROUPS_FOLDER, ENV_TYPE)
    os.makedirs(parent_folder)
    static_groups_env_path = os.path.join(
        parent_folder,
        os.path.join(f'schain-{_schain_name}.json')
    )
    try:
        write_json(static_groups_env_path, STATIC_NODE_GROUPS)
        yield STATIC_NODE_GROUPS
    finally:
        shutil.rmtree(STATIC_GROUPS_FOLDER, ignore_errors=True)
