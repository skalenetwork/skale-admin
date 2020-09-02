import json
import logging
import os
import random
import string
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import contextmanager
from multiprocessing import Process

from skale import Skale
from skale.skale_manager import spawn_skale_manager_lib
from skale.utils.account_tools import generate_account
from skale.utils.account_tools import send_ether
from skale.utils.web3_utils import init_web3
from skale.wallets import BaseWallet, SgxWallet, Web3Wallet
from web3 import Web3

from core.schains.dkg import run_dkg


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

TIMEOUT = 5
NODES_AMOUNT = 2
ETH_AMOUNT = 2.5
SCHAIN_TYPE = 4
SCHAINS_AMOUNT = 1


def generate_random_ip():
    return '.'.join('%s' % random.randint(0, 255) for i in range(4))


def generate_random_port():
    return random.randint(10000, 60000)


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
        exists = cls.is_exists(name)
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
    base_path = os.path.join(BASE_PATH, 'nodes')

    def __init__(self, name: str, wallet: BaseWallet, save: bool = True):
        self.wallet = wallet
        self.name = name
        skale, id = Node.create(name, wallet)
        self.skale = skale
        self.id = id
        self.process = None
        if save:
            self.ensure_base_path()
            self.save()

    def join(self) -> None:
        self.process.join()

    def run_dkg_for_node_schains(self, schains: list) -> None:
        schain_skales = [
            spawn_skale_manager_lib(self.skale)
            for _ in range(len(schains))
        ]
        with ThreadPoolExecutor(max_workers=max(1, len(schains))) as executor:
            futures = [
                executor.submit(
                    run_dkg,
                    skale,
                    schain,
                    id,
                    skale.wallet._key_name
                )
                for skale, schain in zip(schain_skales, schains)
            ]
        for future in as_completed(futures):
            future.result()

    def get_schains_names(self):
        sids = self.skale.schains_internal.get_active_schain_ids_for_node(
            self.id
        )
        print(f'Schains on node {self.id} {sids}')
        return [self.skale.schains.get(sid)['name'] for sid in sids]

    def start_dkg(self) -> None:
        print(f'Starting dkg on node {self.id} {id(self.skale.web3)}')
        schains = self.get_schains_names()
        print(f'Schains on node {self.id} {schains}')
        self.process = Process(
            target=self.run_dkg_for_node_schains,
            args=(schains,)
        )
        self.process.start()

    @classmethod
    def ensure_base_path(cls) -> None:
        if not os.path.isdir(cls.base_path):
            os.makedirs(cls.base_path)

    @classmethod
    def loads(cls, name: str) -> dict:
        filepath = os.path.join(cls.base_path, f'{name}.json')
        with open(filepath) as v_file:
            return json.load(v_file)

    @classmethod
    def is_exists(cls, name: str) -> bool:
        ids = root_skale.nodes.get_active_node_ids()
        names = {root_skale.nodes.get(id_)['name'] for id_ in ids}
        return name in names

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
    def create(cls, name, wallet) -> tuple:
        skale = Skale(ENDPOINT, TEST_ABI_FILEPATH, wallet)
        if cls.is_exists(name):
            data = cls.loads(name)
            id = data['id']
        else:
            ip = generate_random_ip()
            port = generate_random_port()
            skale.manager.create_node(ip=ip, port=port, name=name)
            id = skale.nodes.node_name_to_index(name)
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


def enable_validators(validators: list) -> None:
    for v in validators:
        if not root_skale.validator_service.get(v.id)['trusted']:
            root_skale.validator_service._enable_validator(v.id)


def link_node_wallets_to_validators(wallets: list, validators: list) -> None:
    for wallet, validator in zip(wallets, validators):
        unsigned_hash = Web3.soliditySha3(['uint256'], [validator.id])
        signed_hash = wallet.sign_hash(unsigned_hash.hex())
        signature = signed_hash.signature.hex()
        validator.link_node(wallet.address, signature)


def send_eth_to_addresses(addresses: list, amount: float) -> None:
    for address in addresses:
        send_ether(root_skale.web3, root_skale.wallet, address, amount)


def register_nodes(wallets: list) -> list:
    return [Node(f'node-{i}', wallet) for i, wallet in enumerate(wallets)]


def generate_random_name(len: int = 16) -> None:
    return ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=len))


def create_schains(amount: int) -> None:
    for i in range(amount):
        name = generate_random_name()
        lifetime_seconds = 12 * 3600
        price_in_wei = root_skale.schains.get_schain_price(
            SCHAIN_TYPE, lifetime_seconds)
        root_skale.manager.create_schain(lifetime=lifetime_seconds,
                                         type_of_nodes=SCHAIN_TYPE,
                                         deposit=price_in_wei, name=name)
        time.sleep(TIMEOUT)


def prepare() -> list:
    validators = ensure_validators(NODES_AMOUNT)
    wallets = generate_wallets(NODES_AMOUNT)
    send_eth_to_addresses([w.address for w in wallets], ETH_AMOUNT)
    link_node_wallets_to_validators(wallets, validators)
    enable_validators(validators)
    return register_nodes(wallets)


def run_dkg_test(nodes: list) -> None:
    create_schains(SCHAINS_AMOUNT)
    for node in nodes:
        node.start_dkg()

    for node in nodes:
        node.join()


@contextmanager
def cleanup_schains() -> None:
    try:
        yield
    finally:
        print('Darova')
        schain_ids = root_skale.schains_internal.get_all_schains_ids()
        names = [root_skale.schains.get(sid)['name'] for sid in schain_ids]
        print(names)
        for name in names:
            root_skale.manager.delete_schain(name)


def main() -> None:
    nodes = prepare()
    with cleanup_schains():
        run_dkg_test(nodes)


if __name__ == '__main__':
    main()
