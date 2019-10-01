from core.schains.runner import run_schain_container

DEFAULT_SCHAIN_NAME = 'test'
DEFAULT_SCHAIN_DATA_DIR = '/data_dir'
DEFAULT_SCHAIN_STRUCT = {'name': DEFAULT_SCHAIN_NAME, 'partOfNode': 4}
TEST_CONFIG_FILEPATH = '/skale_node_data/schains/test/config_test.json' # todo!

DEFAULT_SCHAIN_ENV = {
    "SSL_KEY_PATH": 'NULL',
    "SSL_CERT_PATH": 'NULL',
    "HTTP_RPC_PORT": '18880',
    "HTTPS_RPC_PORT": '18881',
    "WS_RPC_PORT": '18882',
    "WSS_RPC_PORT": '18883',

    "SCHAIN_ID": DEFAULT_SCHAIN_NAME,
    "CONFIG_FILE": TEST_CONFIG_FILEPATH,
    "DATA_DIR": DEFAULT_SCHAIN_DATA_DIR
}


def test_run_schain_container(skale):
    container_name = run_schain_container(DEFAULT_SCHAIN_NAME, DEFAULT_SCHAIN_ENV)

