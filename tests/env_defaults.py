import os
import json


def get_json_field(filepath, field) -> str:
    try:
        with open(filepath) as f:
            data = json.load(f)
        return data.get(field)
    except (FileNotFoundError, json.JSONDecodeError):
        return ''


os.environ.setdefault('SKALE_DIR_HOST', os.path.join(os.getcwd(), 'tests/skale-data'))
os.environ.setdefault('SKALE_LIB_PATH', os.path.join(os.getcwd(), 'tests/skale-data/lib'))
os.environ.setdefault('RUNNING_ON_HOST', 'True')
os.environ.setdefault('ENV', 'test')
os.environ.setdefault(
    'SGX_CERTIFICATES_FOLDER', os.path.join(os.getcwd(), 'tests/skale-data/node_data/sgx_certs')
)
os.environ.setdefault('SGX_SERVER_URL', 'https://localhost:1026')
os.environ.setdefault('DB_USER', 'user')
os.environ.setdefault('DB_PASSWORD', 'pass')
os.environ.setdefault('DB_PORT', '3307')
os.environ.setdefault('FLASK_APP_HOST', '0.0.0.0')
os.environ.setdefault('FLASK_APP_PORT', '3008')
os.environ.setdefault('FLASK_DEBUG_MODE', 'True')
os.environ.setdefault('REDIS_URI', 'redis://@127.0.0.1:6379')
os.environ.setdefault('TG_CHAT_ID', '-1231232')
os.environ.setdefault('TG_API_KEY', '123')
os.environ.setdefault('ENV_TYPE', 'devnet')
os.environ.setdefault('ALLOWED_TS_DIFF', '9000000')
os.environ.setdefault('SCHAIN_STOP_TIMEOUT', '1')
os.environ.setdefault('DEFAULT_GAS_PRICE_WEI', '1000000000')

os.environ.setdefault(
    'MANAGER_CONTRACTS',
    get_json_field(
        os.path.join(os.path.dirname(__file__), '../helper-scripts/contracts_data/manager.json'),
        'skale_manager_address',
    ),
)
os.environ.setdefault(
    'IMA_CONTRACTS',
    get_json_field(
        os.path.join(os.path.dirname(__file__), '../helper-scripts/contracts_data/ima.json'),
        'message_proxy_mainnet_address',
    ),
)
os.environ.setdefault(
    'FAIR_CONTRACTS',
    get_json_field(
        os.path.join(os.path.dirname(__file__), '../helper-scripts/contracts_data/fair.json'),
        'Committee',
    ),
)
