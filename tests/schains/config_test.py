from core.schains.config import (
    get_consensus_endpoints_from_config,
    get_snapshots_endpoints_from_config,
    get_skaled_rpc_endpoints_from_config
)
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
                    "insecureBLSPublicKey0": "8",
                    "insecureBLSPublicKey1": "4",
                    "insecureBLSPublicKey2": "4",
                    "insecureBLSPublicKey3": "1",
                    "insecureCommonBLSPublicKey0": "8",
                    "insecureCommonBLSPublicKey1": "4",
                    "insecureCommonBLSPublicKey2": "4",
                    "insecureCommonBLSPublicKey3": "1"
                }
            }
        },
        "sChain": {
            "schainID": 1,
            "schainName": "2chainTest",
            "schainOwner": "0x",
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
                    "owner": "0x",
                    "schainIndex": 2,
                    "ip": "127.0.0.1",
                    "publicIP": "127.0.0.1"
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
                    "owner": "0x",
                    "schainIndex": 2,
                    "ip": "127.0.0.1",
                    "publicIP": "127.0.0.1"
                }
            ]
        }
    }
}


def test_get_consensus_endpoints_from_config():
    assert get_consensus_endpoints_from_config(None) == []
    assert get_consensus_endpoints_from_config(CONFIG) == [
        NodeEndpoint(ip='127.0.0.1', port=10011),
        NodeEndpoint(ip='127.0.0.1', port=10012),
        NodeEndpoint(ip='127.0.0.1', port=10015),
        NodeEndpoint(ip='127.0.0.1', port=10016)
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
