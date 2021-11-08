import pytest

from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_schain_env,
    get_schain_container_cmd
)
from core.schains.config.directory import schain_config_filepath
from core.schains.ssl import get_ssl_filepath
from core.schains.volume import get_schain_volume_config
from tools.configs.containers import SHARED_SPACE_CONTAINER_PATH, SHARED_SPACE_VOLUME_NAME

from tools.configs import SGX_SERVER_URL
from tools.configs.ima import IMA_ENDPOINT


# CONFIG = {
#     "skaleConfig": {
#         "nodeInfo": {
#             "nodeID": 2,
#             "nodeName": "quick-piscis-austrinus",
#             "basePort": 10011,
#             "httpRpcPort": 10013,
#             "httpsRpcPort": 10018,
#             "wsRpcPort": 10014,
#             "wssRpcPort": 10019,
#             "infoHttpRpcPort": 10020,
#             "pgHttpRpcPort": 10100,
#             "pgHttpsRpcPort": 10110,
#             "infoPgHttpRpcPort": 10120,
#             "infoPgHttpsRpcPort": 10130,
#             "bindIP": "127.0.0.1",
#             "imaMessageProxySChain": None,
#             "imaMessageProxyMainNet": "0x",
#             "wallets": {
#                 "ima": {
#                     "url": "https://4",
#                     "keyShareName": "",
#                     "t": 1,
#                     "n": 2,
#                     "BLSPublicKey0": "8",
#                     "BLSPublicKey1": "4",
#                     "BLSPublicKey2": "4",
#                     "BLSPublicKey3": "1",
#                     "commonBLSPublicKey0": "8",
#                     "commonBLSPublicKey1": "4",
#                     "commonBLSPublicKey2": "4",
#                     "commonBLSPublicKey3": "1"
#                 }
#             }
#         },
#         "sChain": {
#             "schainID": 1,
#             "schainName": "2chainTest",
#             "schainOwner": "0x",
#             "previousBlsPublicKeys": [
#                 {
#                     "blsPublicKey0": "8",
#                     "blsPublicKey1": "4",
#                     "blsPublicKey2": "4",
#                     "blsPublicKey3": "1"
#                 }
#             ],
#             "nodes": [
#                 {
#                     "nodeID": 1,
#                     "nodeName": "quick-piscis-austrinus",
#                     "basePort": 10012,
#                     "httpRpcPort": 10014,
#                     "httpsRpcPort": 10019,
#                     "wsRpcPort": 10015,
#                     "wssRpcPort": 10020,
#                     "infoHttpRpcPort": 10021,
#                     "pgHttpRpcPort": 10040,
#                     "pgHttpsRpcPort": 10050,
#                     "infoPgHttpRpcPort": 10060,
#                     "infoPgHttpsRpcPort": 10070,
#                     "publicKey": "0x",
#                     "blsPublicKey0": "8",
#                     "blsPublicKey1": "4",
#                     "blsPublicKey2": "4",
#                     "blsPublicKey3": "1",
#                     "owner": "0x",
#                     "schainIndex": 2,
#                     "ip": "127.0.0.1",
#                     "publicIP": "127.0.0.2"
#                 },
#                 {
#                     "nodeID": 2,
#                     "nodeName": "quick-piscis-austrinus",
#                     "basePort": 10013,
#                     "httpRpcPort": 10015,
#                     "httpsRpcPort": 10020,
#                     "wsRpcPort": 10016,
#                     "wssRpcPort": 10021,
#                     "infoHttpRpcPort": 10090,
#                     "pgHttpRpcPort": 10100,
#                     "pgHttpsRpcPort": 10110,
#                     "infoPgHttpRpcPort": 10120,
#                     "infoPgHttpsRpcPort": 10130,
#                     "publicKey": "0x",
#                     "blsPublicKey0": "8",
#                     "blsPublicKey1": "4",
#                     "blsPublicKey2": "4",
#                     "blsPublicKey3": "1",
#                     "owner": "0x",
#                     "schainIndex": 2,
#                     "ip": "127.0.0.1",
#                     "publicIP": "127.0.0.2"
#                 }
#             ]
#         }
#     }
# }


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
