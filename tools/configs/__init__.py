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
SCHAIN_DATA_PATH = '/skale_schain_data'
CONFIG_FOLDER_NAME = 'config'
CONTRACTS_INFO_FOLDER_NAME = 'contracts_info'

MANAGER_CONTRACTS_INFO_NAME = 'manager.json'
IMA_CONTRACTS_INFO_NAME = 'ima.json'
DKG_CONTRACTS_INFO_NAME = 'dkg.json'

CONTRACTS_INFO_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONTRACTS_INFO_FOLDER_NAME)
CONFIG_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONFIG_FOLDER_NAME)

FLASK_SECRET_KEY_FILENAME = 'flask_db_key.txt'
FLASK_SECRET_KEY_FILE = os.path.join(NODE_DATA_PATH, FLASK_SECRET_KEY_FILENAME)

NODE_CONFIG_FILENAME = 'node_config.json'
NODE_CONFIG_FILEPATH = os.path.join(NODE_DATA_PATH, NODE_CONFIG_FILENAME)

SSL_CERTIFICATES_FILENAME = 'ssl'
SSL_CERTIFICATES_FILEPATH = os.path.join(NODE_DATA_PATH, SSL_CERTIFICATES_FILENAME)

BACKUP_RUN = os.getenv('BACKUP_RUN', False)
SGX_SERVER_URL = os.environ.get('SGX_SERVER_URL')

SGX_URL = urlparse(SGX_SERVER_URL)
SGX_HTTPS_ENABLED = SGX_URL.scheme == 'https'

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

NODE_CONFIG_LOCK_PATH = os.getenv('LOCK_PATH')
if not NODE_CONFIG_LOCK_PATH:
    NODE_CONFIG_LOCK_PATH = '/tmp/skale_node_config.lock'

ROTATION_FLAG_FILENAME = '.rotation'

D_ALLOWED_TIMESTAMP_DIFF = 120
ALLOWED_TIMESTAMP_DIFF = os.getenv('ALLOWED_TIMESTAMP_DIFF', D_ALLOWED_TIMESTAMP_DIFF)
try:
    ALLOWED_TIMESTAMP_DIFF = int(ALLOWED_TIMESTAMP_DIFF)
except TypeError:
    ALLOWED_TIMESTAMP_DIFF = D_ALLOWED_TIMESTAMP_DIFF


REQUIRED_BALANCE_WEI = int(os.getenv('REQURED_BALANCE_WEI') or 10 ** 17)
