import json
import logging
import os

from web3 import Web3

from skale import Skale
from skale.utils.account_tools import generate_account
from skale.utils.account_tools import send_ether
from skale.utils.web3_utils import init_web3
from skale.wallets import BaseWallet, SgxWallet, Web3Wallet


logger = logging.getLogger(__name__)


BASE_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
TEST_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
SGX_SERVER_URL = os.getenv('SGX_SERVER_URL')
SGX_CERTIFICATES_FOLDER = os.path.join(BASE_PATH, 'sgx_certs')


print(ETH_PRIVATE_KEY)
print(ENDPOINT)
print(TEST_ABI_FILEPATH)

NODES_AMOUNT = 4
ETH_AMOUNT = 2.5
PORTS_OFFSET = 11


def init_root_skale() -> Skale:
    web3 = init_web3(ENDPOINT)
    wallet = Web3Wallet(ETH_PRIVATE_KEY, web3)
    return Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)


root_skale = init_root_skale()


class Validator:
    base_path = os.path.join(BASE_PATH, 'validators')

    def __init__(self, name: str, web3: Web3 = None,
                 mda: int = 0, save: bool = True) -> None:
        self.name = name
        skale, private_key = self.create(name, mda=mda, web3=web3)
        self.skale = skale
        self.private_key = private_key
        if save:
            Validator.ensure_base_path()
            self.save()

    @classmethod
    def ensure_base_path(cls) -> None:
        if not os.path.isdir(cls.base_path):
            os.makedirs(cls.base_path)

    @property
    def id(self) -> int:
        return self.skale.validator_service.validator_id_by_address(
            self.address
        )

    @property
    def address(self) -> str:
        return self.skale.wallet.address

    @classmethod
    def is_exists(cls, name: str) -> bool:
        return name in {v['name'] for v in root_skale.validator_service.ls()}

    @classmethod
    def loads(cls, name: str) -> dict:
        filepath = os.path.join(Validator.base_path, f'{name}.json')
        with open(filepath) as v_file:
            return json.load(v_file)

    def save(self, filepath: str = None) -> None:
        fileath = filepath or os.path.join(Validator.base_path,
                                           f'{self.name}.json')
        with open(fileath, 'w') as v_file:
            json.dump(self.to_dict(), v_file)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'id': self.id,
            'address': self.address,
            'private_key': self.private_key
        }

    @classmethod
    def create(cls, name: str, mda: int = 0, web3: Web3 = None) -> tuple:
        web3 = web3 or init_web3(ENDPOINT)
        exists = not cls.is_exists(name)
        if exists:
            account_data = cls.loads(name)
        else:
            account_data = generate_account(web3)
            send_ether(root_skale.web3, root_skale.wallet,
                       account_data['address'], ETH_AMOUNT)
        private_key = account_data['private_key']
        wallet = Web3Wallet(private_key, web3)
        skale = Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)
        if not exists:
            skale.validator_service.register_validator(
                name,
                description=f'Description for {name}',
                fee_rate=0,
                min_delegation_amount=mda
            )
        return skale, private_key

    def link_node(self, address: str, signature: str) -> None:
        self.skale.validator_service.link_node_address(address, signature)


class Node:
    base_path = ''
    base_port = 10000
    ip = '127.0.0.1'
    counter = 0

    def __init__(self, name: str, wallet: BaseWallet):
        self.wallet = wallet
        self.name = name
        skale, id = Node.create(name, wallet)
        self.skale = skale
        self.id = id

    @classmethod
    def loads(cls, name: str) -> dict:
        filepath = os.path.join(cls.base_path, f'{name}.json')
        with open(filepath) as v_file:
            return json.load(v_file)

    @classmethod
    def is_exists(cls, name: str) -> bool:
        ids = root_skale.nodes.get_active_node_ids()
        return name in {v['name'] for v in root_skale.nodes.get_active()}

    def save(self, filepath: str = None) -> None:
        fileath = filepath or os.path.join(self.base_path,
                                           f'{self.name}.json')
        with open(fileath, 'w') as v_file:
            json.dump(self.to_dict(), v_file)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'address': self.wallet.address,
            'id': self.id
        }

    @property
    def address(self) -> str:
        return self.skale.wallet.address

    @classmethod
    def get_available_port(cls):
        return Node.base_port + Node.counter * PORTS_OFFSET

    @classmethod
    def create(cls, name, wallet) -> tuple:
        skale = Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)
        port = Node.get_available_port()
        skale.manager.create_node(ip=Node.ip, port=port, name=name)
        id = skale.nodes.node_name_to_index(name)
        Node.counter += 1
        return skale, id


def ensure_validators(amount: int) -> list:
    return [Validator(f'validator-{i}') for i in range(amount)]


def generate_wallets(amount: int) -> list:
    logger.info(f'Generating {amount} test wallets')
    return [
        SgxWallet(
            SGX_SERVER_URL,
            init_web3(ENDPOINT),
            path_to_cert=SGX_CERTIFICATES_FOLDER
        )
        for _ in range(amount)
    ]


def link_node_wallets_to_validators(wallets: list, validators: list) -> None:
    for wallet, validator in zip(wallets, validators):
        unsigned_hash = Web3.soliditySha3(['uint256'], [validator.id])
        signed_hash = wallet.sign_hash(unsigned_hash.hex())
        signature = signed_hash.signature.hex()
        validator.link_node(wallet.address, signature)


def send_eth_to_addresses(addresses: list, amount: float) -> None:
    for address in addresses:
        send_ether(root_skale.web3, root_skale.wallet, address, amount)


def prepare() -> None:
    validators = ensure_validators(4)
    wallets = generate_wallets(4)
    send_eth_to_addresses([w.address for w in wallets], ETH_AMOUNT)
    link_node_wallets_to_validators(wallets, validators)


def register_nodes(wallets):
    return [Node(f'node-{i}', wallet) for i, wallet in enumerate(wallets)]


def main():
    prepare()


if __name__ == '__main__':
    main()
