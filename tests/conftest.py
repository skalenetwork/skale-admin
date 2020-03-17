import os

import pytest
from skale import Skale
from skale.wallets import Web3Wallet
from skale.utils.web3_utils import init_web3

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.path.join(DIR_PATH, 'test_abi.json')


@pytest.fixture
def skale():
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)
