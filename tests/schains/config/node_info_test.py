import mock

from core.schains.config.static_params import get_static_node_info
from core.schains.config.node_info import generate_wallets_config, generate_current_node_info
from core.schains.types import SchainType
from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH
from tests.utils import get_schain_struct

COMMON_PUBLIC_KEY = [1, 2, 3, 4]

SECRET_KEY_MOCK = {
    'key_share_name': 'BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0',
    't': 1,
    'n': 2,
    'common_public_key': COMMON_PUBLIC_KEY,
    'public_key': ['4', '3', '2', '1'],
}

SCHAIN_NAME = 'test_schain'


def test_generate_wallets_config():
    with mock.patch('core.schains.config.node_info.read_json', return_value=SECRET_KEY_MOCK):
        wallets = generate_wallets_config(
            'test_schain',
            0,
            sync_node=False,
            nodes_in_schain=4,
            common_bls_public_keys=COMMON_PUBLIC_KEY
        )

    assert wallets['ima']['keyShareName'] == SECRET_KEY_MOCK['key_share_name']
    assert wallets['ima']['certFile'] == SGX_SSL_CERT_FILEPATH
    assert wallets['ima']['keyFile'] == SGX_SSL_KEY_FILEPATH
    assert wallets['ima']['commonBLSPublicKey0'] == '1'
    assert wallets['ima']['commonBLSPublicKey1'] == '2'
    assert wallets['ima']['commonBLSPublicKey2'] == '3'
    assert wallets['ima']['commonBLSPublicKey3'] == '4'
    assert wallets['ima']['BLSPublicKey0'] == '4'
    assert wallets['ima']['BLSPublicKey1'] == '3'
    assert wallets['ima']['BLSPublicKey2'] == '2'
    assert wallets['ima']['BLSPublicKey3'] == '1'


def test_generate_wallets_config_sync_node():
    with mock.patch('core.schains.config.node_info.read_json', return_value=SECRET_KEY_MOCK):
        wallets = generate_wallets_config(
            'test_schain',
            0,
            sync_node=True,
            nodes_in_schain=4,
            common_bls_public_keys=COMMON_PUBLIC_KEY
        )

    assert 'keyShareName' not in wallets['ima']
    assert 'certFile' not in wallets['ima']
    assert 'keyFile' not in wallets['ima']
    assert 'BLSPublicKey0' not in wallets['ima']
    assert 'BLSPublicKey1' not in wallets['ima']
    assert 'BLSPublicKey2' not in wallets['ima']
    assert 'BLSPublicKey3' not in wallets['ima']
    assert wallets['ima']['commonBLSPublicKey0'] == '1'
    assert wallets['ima']['commonBLSPublicKey1'] == '2'
    assert wallets['ima']['commonBLSPublicKey2'] == '3'
    assert wallets['ima']['commonBLSPublicKey3'] == '4'


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
            schain=get_schain_struct(schain_name=_schain_name),
            rotation_id=0,
            skale_manager_opts=skale_manager_opts,
            nodes_in_schain=4,
            schain_base_port=10000,
            common_bls_public_keys=COMMON_PUBLIC_KEY
        )
    current_node_info_dict = current_node_info.to_dict()
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
            schain=get_schain_struct(schain_name=_schain_name),
            rotation_id=0,
            skale_manager_opts=skale_manager_opts,
            nodes_in_schain=4,
            schain_base_port=10000,
            common_bls_public_keys=COMMON_PUBLIC_KEY
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
            schain=get_schain_struct(schain_name=_schain_name),
            rotation_id=0,
            skale_manager_opts=skale_manager_opts,
            nodes_in_schain=4,
            schain_base_port=10000,
            common_bls_public_keys=COMMON_PUBLIC_KEY
        )
        current_node_info_dict = current_node_info.to_dict()
        assert current_node_info_dict['skale-manager'] == {
            'SchainsInternal': '0x1656',
            'Nodes': '0x7742'
        }
