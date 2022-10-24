import mock

from core.schains.config.helper import get_static_schain_params
from core.schains.config.node_info import (
    generate_wallets_config, get_rotate_after_block, generate_current_node_info
)
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
        wallets = generate_wallets_config('test_schain', 0)

    assert wallets['ima']['keyShareName'] == SECRET_KEY_MOCK['key_share_name']
    assert wallets['ima']['certFile'] == SGX_SSL_CERT_FILEPATH
    assert wallets['ima']['keyFile'] == SGX_SSL_KEY_FILEPATH
    assert wallets['ima']['commonBLSPublicKey0'] == '1'
    assert wallets['ima']['commonBLSPublicKey1'] == '1'
    assert wallets['ima']['commonBLSPublicKey2'] == '1'
    assert wallets['ima']['BLSPublicKey0'] == '1'
    assert wallets['ima']['BLSPublicKey1'] == '1'
    assert wallets['ima']['BLSPublicKey2'] == '1'


def test_get_rotate_after_block():
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='mainnet'):
        assert get_rotate_after_block('test4') == 1024000
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='testnet'):
        assert get_rotate_after_block('medium') == 102400
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='devnet'):
        assert get_rotate_after_block('medium') == 40960
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='qanet'):
        assert get_rotate_after_block('small') == 25600
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='testnet'):
        assert get_rotate_after_block('large') == 3276803


def test_generate_current_node_info(skale_manager_opts, schain_config, _schain_name):
    static_schain_params = get_static_schain_params()
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='testnet'):
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_schain_params=static_schain_params,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            skale_manager_opts=skale_manager_opts
        )
    current_node_info_dict = current_node_info.to_dict()
    assert current_node_info_dict['nodeID'] == 1
    assert current_node_info_dict['nodeName'] == 'test'
    assert current_node_info_dict['basePort'] == 10000
    assert current_node_info_dict['httpRpcPort'] == 10003
    assert current_node_info_dict['httpsRpcPort'] == 10008
    assert current_node_info_dict['wsRpcPort'] == 10002
    assert current_node_info_dict['infoHttpRpcPort'] == 10009
    assert current_node_info_dict['minCacheSize'] == 32000000
    assert current_node_info_dict['maxCacheSize'] == 64000000
    assert current_node_info_dict['collectionQueueSize'] == 20
    assert current_node_info_dict['rotateAfterBlock'] == 102400

    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='mainnet'):
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_schain_params=static_schain_params,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            skale_manager_opts=skale_manager_opts
        )
    current_node_info_dict = current_node_info.to_dict()
    assert current_node_info_dict['rotateAfterBlock'] == 1024000


def test_skale_manager_opts(skale_manager_opts, schain_config, _schain_name):
    static_schain_params = get_static_schain_params()
    with mock.patch('core.schains.config.node_info.ENV_TYPE', new='testnet'):
        current_node_info = generate_current_node_info(
            node={'name': 'test', 'port': 10000},
            node_id=1,
            ecdsa_key_name='123',
            static_schain_params=static_schain_params,
            schain={'name': _schain_name, 'partOfNode': 0},
            schains_on_node=[{'name': _schain_name, 'port': 10000}],
            rotation_id=0,
            skale_manager_opts=skale_manager_opts
        )
        current_node_info_dict = current_node_info.to_dict()
        assert current_node_info_dict['skale-manager'] == {
            'SchainsInternal': '0x1656',
            'Nodes': '0x7742'
        }
