import pytest

from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_schain_env,
    get_schain_container_cmd,
    get_schain_container_sync_opts
)
from core.schains.config.directory import schain_config_filepath
from core.schains.ssl import get_ssl_filepath
from core.schains.volume import get_schain_volume_config
from tools.configs.containers import SHARED_SPACE_CONTAINER_PATH, SHARED_SPACE_VOLUME_NAME

from tools.configs import SGX_SERVER_URL
from tools.configs.ima import IMA_ENDPOINT


def test_get_node_ips_from_config(schain_config):
    assert get_node_ips_from_config(schain_config) == \
        ['127.0.0.1', '127.0.0.2']


def test_get_base_port_from_config(schain_config):
    assert get_base_port_from_config(schain_config) == 10000


def test_get_own_ip_from_config(schain_config):
    assert get_own_ip_from_config(schain_config) == '127.0.0.1'


def test_get_schain_container_cmd(schain_config, cert_key_pair):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_schain_container_cmd(schain_name)
    config_filepath = schain_config_filepath(schain_name, in_schain_container=True)
    ssl_key_path, ssl_cert_path = get_ssl_filepath()
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 2 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path}'
    )
    assert container_opts == expected_opts

    container_opts = get_schain_container_cmd(schain_name, enable_ssl=False)
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 2 --web3-trace '
        f'--enable-debug-behavior-apis --aa no'
    )
    assert container_opts == expected_opts


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
        SHARED_SPACE_VOLUME_NAME: {'bind': SHARED_SPACE_CONTAINER_PATH, 'mode': 'rw'}
    }
    volume_config = get_schain_volume_config('test_name',
                                             '/mnt/mount_path/', mode='Z')
    assert volume_config == {
        'test_name': {'bind': '/mnt/mount_path/', 'mode': 'Z'},
        SHARED_SPACE_VOLUME_NAME: {'bind': SHARED_SPACE_CONTAINER_PATH, 'mode': 'Z'}
    }


def test_get_schain_container_sync_opts():
    sync_opts = get_schain_container_sync_opts(start_ts=123)
    assert sync_opts == [
        '--download-snapshot readfromconfig',
        '--start-timestamp 123'
    ]
    sync_opts = get_schain_container_sync_opts()
    assert sync_opts == [
        '--download-snapshot readfromconfig'
    ]
