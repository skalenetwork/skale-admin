import os
from tools.configs import CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME

IMA_ENDPOINT = os.environ['MTA_ENDPOINT']

PROXY_ABI_FILENAME = 'proxy.json'
MAINNET_PROXY_PATH = os.path.join(CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME)
