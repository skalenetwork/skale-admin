import mock

from core.schains.config.static_params import get_static_node_info
from core.schains.config.node_info import generate_wallets_config, generate_current_node_info
from core.schains.types import SchainType
from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH

SECRET_KEY_MOCK = {
    'key_share_name': 'BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0',
    't': 1,
    'n': 2,
    'common_public_key': [1, 1, 1],
    'public_key': ['1', '1', '1'],
}

SCHAIN_NAME = 'test_schain'


def test_generate_wallets_config():
    with mock.patch('core.schains.config.node_info.read_json', return_value=SECRET_KEY_MOCK):
        wallets = generate_wallets_config('test_schain', 0, 4)

        assert wallets['ima']['keyShareName'] == SECRET_KEY_MOCK['key_share_name']
        assert wallets['ima']['certFile'] == SGX_SSL_CERT_FILEPATH
        assert wallets['ima']['keyFile'] == SGX_SSL_KEY_FILEPATH
        assert wallets['ima']['n'] == 4
        assert wallets['ima']['commonBLSPublicKey0'] == '1'
        assert wallets['ima']['commonBLSPublicKey1'] == '1'
        assert wallets['ima']['commonBLSPublicKey2'] == '1'
        assert wallets['ima']['BLSPublicKey0'] == '1'
        assert wallets['ima']['BLSPublicKey1'] == '1'
        assert wallets['ima']['BLSPublicKey2'] == '1'

    with mock.patch('core.schains.config.node_info.read_json', return_value=SECRET_KEY_MOCK):
        wallets = generate_wallets_config('test_schain', 0, 4, sync_node=True)
        assert wallets['ima']['n'] == 4


def test_generate_current_node_info(
    skale_manager_opts,
    schain_config,
    _schain_name,
    predeployed_ima
):
    with mock.patch('core.schains.config.static_params.ENV_TYPE', new='testnet'):
        static_node_info = get_static_node_info(SchainType.medium)
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_node_info=static_node_info,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            nodes_in_schain=5,
            skale_manager_opts=skale_manager_opts
        )
    current_node_info_dict = current_node_info.to_dict()
    assert current_node_info_dict['wallets']['ima']['n'] == 5
    assert current_node_info_dict['nodeID'] == 1
    assert current_node_info_dict['nodeName'] == 'test'
    assert current_node_info_dict['basePort'] == 10000
    assert current_node_info_dict['httpRpcPort'] == 10003
    assert current_node_info_dict['httpsRpcPort'] == 10008
    assert current_node_info_dict['wsRpcPort'] == 10002
    assert current_node_info_dict['infoHttpRpcPort'] == 10009
    assert current_node_info_dict['minCacheSize'] == 8000000
    assert current_node_info_dict['maxCacheSize'] == 16000000
    assert current_node_info_dict['collectionQueueSize'] == 20

    with mock.patch('core.schains.config.static_params.ENV_TYPE', new='mainnet'):
        static_node_info = get_static_node_info(SchainType.medium)
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_node_info=static_node_info,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            nodes_in_schain=4,
            skale_manager_opts=skale_manager_opts
        )
    current_node_info_dict = current_node_info.to_dict()
    assert current_node_info_dict['maxCacheSize'] == 16000000
    assert current_node_info_dict['skale-manager'] == {
        'SchainsInternal': '0x1656',
        'Nodes': '0x7742'
    }


def test_skale_manager_opts(
    skale_manager_opts,
    schain_config,
    _schain_name,
    predeployed_ima
):
    with mock.patch('core.schains.config.static_params.ENV_TYPE', new='testnet'):
        static_node_info = get_static_node_info(SchainType.medium)
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_node_info=static_node_info,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            nodes_in_schain=4,
            skale_manager_opts=skale_manager_opts
        )
        current_node_info_dict = current_node_info.to_dict()
        assert current_node_info_dict['skale-manager'] == {
            'SchainsInternal': '0x1656',
            'Nodes': '0x7742'
        }
