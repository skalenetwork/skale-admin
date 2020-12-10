import mock

from core.schains.config.node_info import generate_wallets_config
from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH, SGX_SERVER_URL

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

    assert wallets['ima']['url'] == SGX_SERVER_URL
    assert wallets['ima']['keyShareName'] == SECRET_KEY_MOCK['key_share_name']
    assert wallets['ima']['certFile'] == SGX_SSL_CERT_FILEPATH
    assert wallets['ima']['keyFile'] == SGX_SSL_KEY_FILEPATH
    assert wallets['ima']['commonBLSPublicKey0'] == '1'
    assert wallets['ima']['commonBLSPublicKey1'] == '1'
    assert wallets['ima']['commonBLSPublicKey2'] == '1'
    assert wallets['ima']['BLSPublicKey0'] == '1'
    assert wallets['ima']['BLSPublicKey1'] == '1'
    assert wallets['ima']['BLSPublicKey2'] == '1'
