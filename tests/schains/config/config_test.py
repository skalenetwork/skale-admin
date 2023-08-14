import os

import pytest

from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_schain_env
)
from core.schains.config.directory import schain_config_dir
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.main import get_finish_ts, get_rotation_ids_from_config
from core.schains.volume import get_schain_volume_config
from tools.configs.containers import SHARED_SPACE_CONTAINER_PATH, SHARED_SPACE_VOLUME_NAME


def test_get_node_ips_from_config(schain_config):
    assert get_node_ips_from_config(schain_config) == \
        ['127.0.0.1', '127.0.0.2']


def test_get_base_port_from_config(schain_config):
    assert get_base_port_from_config(schain_config) == 10000


def test_get_own_ip_from_config(schain_config):
    assert get_own_ip_from_config(schain_config) == '127.0.0.1'


def test_get_schain_env():
    expected_env = {"SEGFAULT_SIGNALS": 'all'}
    assert get_schain_env() == expected_env
    expected_env = {"SEGFAULT_SIGNALS": 'all', 'NO_ULIMIT_CHECK': 1}
    assert get_schain_env(ulimit_check=False) == expected_env


@pytest.mark.skip(reason="shared space is temporarily disabled")
def test_get_schain_volume_config():
    volume_config = get_schain_volume_config('test_name', '/mnt/mount_path/')
    assert volume_config == {
        'test_name': {'bind': '/mnt/mount_path/', 'mode': 'rw'},
        SHARED_SPACE_VOLUME_NAME: {
            'bind': SHARED_SPACE_CONTAINER_PATH, 'mode': 'rw'}
    }
    volume_config = get_schain_volume_config('test_name',
                                             '/mnt/mount_path/', mode='Z')
    assert volume_config == {
        'test_name': {'bind': '/mnt/mount_path/', 'mode': 'Z'},
        SHARED_SPACE_VOLUME_NAME: {
            'bind': SHARED_SPACE_CONTAINER_PATH, 'mode': 'Z'}
    }


def test_get_schain_upstream_config(schain_db, upstreams):
    name = schain_db
    cfm = ConfigFileManager(schain_name=name)
    upstream_config = cfm.latest_upstream_path
    config_folder = schain_config_dir(name)
    expected = os.path.join(
        config_folder, f'schain_{name}_11_1687183339.json')
    assert upstream_config == expected

    not_existing_chain = 'not-exist'
    cfm = ConfigFileManager(not_existing_chain)
    assert not cfm.upstream_config_exists()
    assert cfm.latest_upstream_config is None


def test_get_finish_ts(schain_config):
    finish_ts = get_finish_ts(schain_config)
    assert finish_ts == 1687180291

    schain_config['skaleConfig']['sChain']['nodeGroups'].pop('0')
    finish_ts = get_finish_ts(schain_config)
    assert finish_ts is None


def test_get_rotation_ids_from_config(schain_config):
    ids = get_rotation_ids_from_config(schain_config)
    assert ids == [0, 1]
