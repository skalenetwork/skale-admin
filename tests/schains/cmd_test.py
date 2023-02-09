from core.schains.cmd import (
    get_schain_container_cmd,
    get_schain_container_sync_opts
)
from core.schains.config.directory import schain_config_filepath
from core.schains.ssl import get_ssl_filepath
from tools.configs.containers import SHARED_SPACE_CONTAINER_PATH

from tools.configs import SGX_SERVER_URL
from tools.configs.ima import IMA_ENDPOINT
from tools.configs.web3 import ENDPOINT


def test_get_schain_container_cmd(schain_config, cert_key_pair):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_schain_container_cmd(schain_name)
    config_filepath = schain_config_filepath(schain_name, in_schain_container=True)
    ssl_key_path, ssl_cert_path = get_ssl_filepath()
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 3 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path}'
    )
    assert container_opts == expected_opts

    container_opts = get_schain_container_cmd(schain_name, enable_ssl=False)
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 3 --web3-trace '
        f'--enable-debug-behavior-apis --aa no'
    )
    assert container_opts == expected_opts

    container_opts = get_schain_container_cmd(schain_name, snapshot_from='1.1.1.1')
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 3 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path} '
        '--no-snapshot-majority 1.1.1.1'
    )
    assert container_opts == expected_opts

    container_opts = get_schain_container_cmd(schain_name, snapshot_from='')
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --sgx-url {SGX_SERVER_URL} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        f'--main-net-url {IMA_ENDPOINT} -v 3 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path}'
    )
    assert container_opts == expected_opts


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


def test_get_schain_container_cmd_sync_node(schain_config, cert_key_pair):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_schain_container_cmd(schain_name, enable_ssl=False, sync_node=True)
    config_filepath = schain_config_filepath(schain_name, in_schain_container=True)

    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {ENDPOINT} '
        f'-v 3 --web3-trace --enable-debug-behavior-apis --aa no'
    )
    assert container_opts == expected_opts
