import json
import os
import pathlib
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from skale import SkaleManager
from skale.types.schain import SchainHash, SchainName

import tests.env_defaults  # noqa: F401 # set default env variables for tests
from core.chain.status import (
    init_node_cli_status,
    node_cli_status_filepath,
)
from core.config.endpoint import get_base_port_from_config
from core.config.schain.directory import schain_config_dir
from core.config.schain.helper import (
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.ima.container import ImaData
from core.manager_cache import ManagerCache
from core.node import get_current_nodes
from core.node_config import NodeConfig
from core.schains.external_config import ExternalConfig, ExternalState
from tests.utils import (
    ALLOWED_RANGES,
    CONFIG_STREAM,
    CURRENT_TS,
    IMA_MIGRATION_TS,
    generate_cert,
    generate_schain_config,
    get_test_rule_controller,
    upsert_schain_record_with_config,
)
from tools.configs import (
    CONFIG_FOLDER,
    ENV_TYPE,
    META_FILEPATH,
    SSL_CERTIFICATES_FILEPATH,
)
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.helper import write_json
from web.models.schain import SChainRecord, create_tables

pytest_plugins = ['tests.fixtures.web3', 'tests.fixtures.schain', 'tests.fixtures.containers']


@pytest.fixture
def ssl_folder():
    pathlib.Path(SSL_CERTIFICATES_FILEPATH).mkdir(parents=True, exist_ok=True)
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


SECRET_KEY = {
    'common_public_key': [
        11111111111111111111111111111111111111111111111111111111111111111111111111111,
        1111111111111111111111111111111111111111111111111111111111111111111111111111,
        1111111111111111111111111111111111111111111111111111111111111111111111111111,
        11111111111111111111111111111111111111111111111111111111111111111111111111111,
    ],
    'public_key': [
        '1111111111111111111111111111111111111111111111111111111111111111111111111111',
        '1111111111111111111111111111111111111111111111111111111111111111111111111111',
        '1111111111111111111111111111111111111111111111111111111111111111111111111111',
        '11111111111111111111111111111111111111111111111111111111111111111111111111111',
    ],
    'bls_public_keys': [
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
        '1111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111:11111111111111111111111111111111111111111111111111111111111111111111111111111',  # noqa
    ],
    't': 11,
    'n': 16,
    'key_share_name': 'BLS_KEY:SCHAIN_ID:33333333333333333333333333333333333333333333333333333333333333333333333333333:NODE_ID:0:DKG_ID:0',  # noqa
}


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
def schain_config(_schain_name, secret_key):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    config_path = os.path.join(schain_dir_path, f'schain_{_schain_name}.json')
    try:
        pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
        schain_config = generate_schain_config(_schain_name)
        with open(config_path, 'w') as config_file:
            json.dump(schain_config, config_file)
        yield schain_config
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def remove_schain_config_file(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    config_path = os.path.join(schain_dir_path, f'schain_{_schain_name}.json')
    if os.path.exists(config_path):
        os.remove(config_path)


def rm_schain_dir(schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, schain_name)
    # fix permission denied after schain container running
    subprocess.run(['rm', '-rf', schain_dir_path])


@pytest.fixture
def db():
    create_tables()
    try:
        yield
    finally:
        SChainRecord.drop_table()


@pytest.fixture
def schain_db(db, _schain_name, meta_file):
    """Database with default schain inserted"""
    upsert_schain_record_with_config(_schain_name)
    return _schain_name


@pytest.fixture
def meta_file():
    meta_info = {'version': '0.0.0', 'config_stream': CONFIG_STREAM, 'docker_lvmpy_stream': '1.1.1'}
    with open(META_FILEPATH, 'w') as meta_file:
        json.dump(meta_info, meta_file)
    try:
        yield meta_info
    finally:
        os.remove(META_FILEPATH)


@pytest.fixture
def node_config(skale, nodes):
    node_config = NodeConfig()
    node_config.id = nodes[0]
    return node_config


@pytest.fixture
def ima_data(skale):
    return ImaData(linked=True, chain_id=skale.web3.eth.chain_id)


@pytest.fixture
def rule_controller(_schain_name, schain_db, schain_config):
    base_port = get_base_port_from_config(schain_config)
    own_ip = get_own_ip_from_config(schain_config)
    node_ips = get_node_ips_from_config(schain_config)
    return get_test_rule_controller(
        name=_schain_name, base_port=base_port, own_ip=own_ip, node_ips=node_ips
    )


@pytest.fixture
def synced_rule_controller(rule_controller):
    rule_controller.sync()
    return rule_controller


@pytest.fixture
def uninited_rule_controller(_schain_name):
    return get_test_rule_controller(name=_schain_name)


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
    return ExternalState(ima_linked=True, chain_id=skale.web3.eth.chain_id, ranges=ALLOWED_RANGES)


@pytest.fixture
def econfig(schain_db, estate):
    name = schain_db
    ec = ExternalConfig(name)
    ec.update(estate)
    return ec


@pytest.fixture
def current_nodes(
    skale: SkaleManager,
    schain_db: SchainName,
    schain_hash_on_contracts: SchainHash,
    manager_cache: ManagerCache,
):
    return get_current_nodes(skale, schain_hash_on_contracts, manager_cache=manager_cache)


@pytest.fixture
def upstreams(schain_db, schain_config):
    name = schain_db
    config_folder = schain_config_dir(name)
    files = [
        f'schain_{name}_10_1687183338.json',
        f'schain_{name}_9_1687183335.json',
        f'schain_{name}_11_1687183336.json',
        f'schain_{name}_11_1687183337.json',
        f'schain_{name}_11_1687183339.json',
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


NCLI_STATUS_DICT = {'repair_ts': CURRENT_TS, 'snapshot_from': '127.0.0.1'}


@pytest.fixture
def ncli_status(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    ncli_status_path = node_cli_status_filepath(_schain_name)
    write_json(ncli_status_path, NCLI_STATUS_DICT)

    try:
        yield init_node_cli_status(_schain_name)
    finally:
        shutil.rmtree(schain_dir_path, ignore_errors=True)


@pytest.fixture()
def nft_chain_folder():
    path = '/etc/nft.conf.d/skale/chains'
    try:
        os.makedirs(path)
        yield path
    finally:
        shutil.rmtree(path)
