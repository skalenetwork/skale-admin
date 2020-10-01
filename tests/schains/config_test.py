from core.schains.config.helper import (
    get_consensus_endpoints_from_config,
    get_snapshots_endpoints_from_config,
    get_skaled_rpc_endpoints_from_config,
    get_schain_container_cmd
)
from core.schains.helper import get_schain_config_filepath
from core.schains.ssl import get_ssl_filepath

from tools.iptables import NodeEndpoint


CONFIG = {
    "skaleConfig": {
        "nodeInfo": {
            "nodeID": 2,
            "nodeName": "quick-piscis-austrinus",
            "basePort": 10011,
            "httpRpcPort": 10013,
            "httpsRpcPort": 10018,
            "wsRpcPort": 10014,
            "wssRpcPort": 10019,
            "bindIP": "127.0.0.1",
            "imaMainNet": "wss://12.com",
            "imaMessageProxySChain": None,
            "imaMessageProxyMainNet": "0x",
            "wallets": {
                "ima": {
                    "url": "https://4",
                    "keyShareName": "",
                    "t": 1,
                    "n": 2,
                    "BLSPublicKey0": "8",
                    "BLSPublicKey1": "4",
                    "BLSPublicKey2": "4",
                    "BLSPublicKey3": "1",
                    "commonBLSPublicKey0": "8",
                    "commonBLSPublicKey1": "4",
                    "commonBLSPublicKey2": "4",
                    "commonBLSPublicKey3": "1"
                }
            }
        },
        "sChain": {
            "schainID": 1,
            "schainName": "2chainTest",
            "schainOwner": "0x",
            "previousBlsPublicKeys": [
                {
                    "blsPublicKey0": "8",
                    "blsPublicKey1": "4",
                    "blsPublicKey2": "4",
                    "blsPublicKey3": "1"
                }
            ],
            "nodes": [
                {
                    "nodeID": 1,
                    "nodeName": "quick-piscis-austrinus",
                    "basePort": 10012,
                    "httpRpcPort": 10014,
                    "httpsRpcPort": 10019,
                    "wsRpcPort": 10015,
                    "wssRpcPort": 10020,
                    "publicKey": "0x",
                    "blsPublicKey0": "8",
                    "blsPublicKey1": "4",
                    "blsPublicKey2": "4",
                    "blsPublicKey3": "1",
                    "owner": "0x",
                    "schainIndex": 2,
                    "ip": "127.0.0.1",
                    "publicIP": "127.0.0.2"
                },
                {
                    "nodeID": 2,
                    "nodeName": "quick-piscis-austrinus",
                    "basePort": 10013,
                    "httpRpcPort": 10015,
                    "httpsRpcPort": 10020,
                    "wsRpcPort": 10016,
                    "wssRpcPort": 10021,
                    "publicKey": "0x",
                    "blsPublicKey0": "8",
                    "blsPublicKey1": "4",
                    "blsPublicKey2": "4",
                    "blsPublicKey3": "1",
                    "owner": "0x",
                    "schainIndex": 2,
                    "ip": "127.0.0.1",
                    "publicIP": "127.0.0.2"
                }
            ]
        }
    }
}


def test_get_consensus_endpoints_from_config():
    assert get_consensus_endpoints_from_config(None) == []
    assert get_consensus_endpoints_from_config(CONFIG) == [
        NodeEndpoint(ip='127.0.0.2', port=10011),
        NodeEndpoint(ip='127.0.0.2', port=10012),
        NodeEndpoint(ip='127.0.0.2', port=10015),
        NodeEndpoint(ip='127.0.0.2', port=10016)
    ]


def test_get_skaled_rpc_endpoinds_from_config():
    assert get_skaled_rpc_endpoints_from_config(None) == []
    assert get_skaled_rpc_endpoints_from_config(CONFIG) == [
        NodeEndpoint(ip=None, port=10013),
        NodeEndpoint(ip=None, port=10014),
        NodeEndpoint(ip=None, port=10018),
        NodeEndpoint(ip=None, port=10019)
    ]


def test_get_snapshots_endpoints_from_config():
    assert get_snapshots_endpoints_from_config(None) == []
    assert get_snapshots_endpoints_from_config(CONFIG) == []


def test_get_schain_container_cmd(schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_schain_container_cmd(schain_name)
    config_filepath = get_schain_config_filepath(schain_name, in_schain_container=True)
    ssl_key_path, ssl_cert_path = get_ssl_filepath()
    opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 2234 '
        f'--https-port 10002 --ws-port 10003 --wss-port 10008 --ssl-key {ssl_key_path} '
        f'--ssl-cert {ssl_cert_path} -v 4 --web3-trace --enable-debug-behavior-apis --aa no '
    )
    assert container_opts == opts
