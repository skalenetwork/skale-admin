import os
from urllib.parse import urlparse

LONG_LINE = '=' * 100

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

RUNNING_ON_HOST = os.getenv('RUNNING_ON_HOST', False)
SKALE_DIR_HOST = os.getenv('SKALE_DIR_HOST')
NODE_DATA_PATH_HOST = os.path.join(SKALE_DIR_HOST, 'node_data')

if RUNNING_ON_HOST:
    SKALE_VOLUME_PATH = SKALE_DIR_HOST
    NODE_DATA_PATH = NODE_DATA_PATH_HOST
else:
    SKALE_VOLUME_PATH = '/skale_vol'
    NODE_DATA_PATH = '/skale_node_data'

SCHAIN_NODE_DATA_PATH = '/skale_node_data'
SCHAIN_CONFIG_DIR_SKALED = '/schain_config'
CONFIG_FOLDER_NAME = 'config'
CONTRACTS_INFO_FOLDER_NAME = 'contracts_info'
SKALE_LIB_PATH = os.getenv('SKALE_LIB_PATH', '/var/lib/skale')

MANAGER_CONTRACTS_INFO_NAME = 'manager.json'
IMA_CONTRACTS_INFO_NAME = 'ima.json'
DKG_CONTRACTS_INFO_NAME = 'dkg.json'

CONTRACTS_INFO_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONTRACTS_INFO_FOLDER_NAME)
CONFIG_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONFIG_FOLDER_NAME)

STATIC_ACCOUNTS_FOLDER = os.path.join(CONFIG_FOLDER, 'schain_accounts')

FLASK_SECRET_KEY_FILENAME = 'flask_db_key.txt'
FLASK_SECRET_KEY_FILE = os.path.join(NODE_DATA_PATH, FLASK_SECRET_KEY_FILENAME)

NODE_CONFIG_FILENAME = 'node_config.json'
NODE_CONFIG_FILEPATH = os.path.join(NODE_DATA_PATH, NODE_CONFIG_FILENAME)

SSL_CERTIFICATES_FILENAME = 'ssl'
SSL_CERTIFICATES_FILEPATH = os.path.join(NODE_DATA_PATH, SSL_CERTIFICATES_FILENAME)

SSL_KEY_NAME = 'ssl_key'
SSL_CRT_NAME = 'ssl_cert'

SSL_KEY_PATH = os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_KEY_NAME)
SSL_CERT_PATH = os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_CRT_NAME)

BACKUP_RUN = os.getenv('BACKUP_RUN', False)
SGX_SERVER_URL = os.environ.get('SGX_SERVER_URL')

PARSED_SGX_URL = urlparse(SGX_SERVER_URL)
SGX_HTTPS_ENABLED = PARSED_SGX_URL.scheme == 'https'

SGX_CERTIFICATES_FOLDER_NAME = os.getenv('SGX_CERTIFICATES_DIR_NAME')
SGX_SSL_KEY_NAME = 'sgx.key'
SGX_SSL_CERT_NAME = 'sgx.crt'

if SGX_CERTIFICATES_FOLDER_NAME:
    SGX_CERTIFICATES_FOLDER = os.path.join(NODE_DATA_PATH, SGX_CERTIFICATES_FOLDER_NAME)
else:
    SGX_CERTIFICATES_FOLDER = os.getenv('SGX_CERTIFICATES_FOLDER')

if SGX_HTTPS_ENABLED and SGX_CERTIFICATES_FOLDER:
    SGX_SSL_KEY_FILEPATH = os.path.join(SGX_CERTIFICATES_FOLDER, SGX_SSL_KEY_NAME)
    SGX_SSL_CERT_FILEPATH = os.path.join(SGX_CERTIFICATES_FOLDER, SGX_SSL_CERT_NAME)
else:
    SGX_SSL_KEY_FILEPATH = None
    SGX_SSL_CERT_FILEPATH = None

NODE_CONFIG_LOCK_PATH = os.getenv('NODE_CONFIG_LOCK_PATH')
if not NODE_CONFIG_LOCK_PATH:
    NODE_CONFIG_LOCK_PATH = os.path.join(NODE_DATA_PATH,
                                         'node_config.lock')
INIT_LOCK_PATH = os.getenv('INIT_LOCK_PATH')
if not INIT_LOCK_PATH:
    INIT_LOCK_PATH = os.path.join(NODE_DATA_PATH, 'init.lock')

META_FILEPATH = os.path.join(NODE_DATA_PATH, 'meta.json')

ALLOWED_TIMESTAMP_DIFF = int(os.getenv('ALLOWED_TIMESTAMP_DIFF', 120))

ENV_TYPE = os.environ.get('ENV_TYPE')
ALLOCATION_FILEPATH = os.path.join(CONFIG_FOLDER, 'schain_allocation.yml')

STATIC_PARAMS_FILEPATH = os.path.join(CONFIG_FOLDER, 'static_params.yaml')

DEFAULT_POOL = 'transactions'

WATCHDOG_PORT = 3009

ZMQ_PORT = 1031
ZMQ_TIMEOUT = 5

CHECK_REPORT_PATH = os.path.join(SKALE_VOLUME_PATH, 'reports', 'checks.json')

NODE_OPTIONS_FILEPATH = os.path.join(NODE_DATA_PATH, 'node_options.json')
NODE_DOCKER_CONFIG_PATH = os.path.join(NODE_DATA_PATH, 'docker.json')

PULL_CONFIG_FOR_SCHAIN = os.getenv('PULL_CONFIG_FOR_SCHAIN')

CHANGE_IP_DELAY = 300

STATSD_HOST = '127.0.0.1'
STATSD_PORT = 8125
SYNC_NODE = os.getenv('SYNC_NODE') == 'True'
