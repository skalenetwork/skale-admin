import logging
import json
import os
import random
import shutil
import string
import time
from pathlib import Path
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import contextmanager
# from multiprocessing import Process as Thread
from shutil import copyfile
from threading import Thread

import docker
from sgx import SgxClient
from skale import Skale
from skale.skale_manager import spawn_skale_manager_lib
from skale.utils.account_tools import generate_account, send_ether
# from skale.utils.helper import init_default_logger
from skale.utils.web3_utils import init_web3
from skale.wallets import RPCWallet, SgxWallet, Web3Wallet
from web3 import Web3

from core.schains.dkg import run_dkg
from tools.logger import init_admin_logger


logger = logging.getLogger(__name__)

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
ENDPOINT = os.getenv('ENDPOINT')
TEST_ABI_FILEPATH = os.getenv('TEST_ABI_FILEPATH')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
SGX_SERVER_URL = os.getenv('SGX_SERVER_URL')
SGX_CERTIFICATES_FOLDER = os.getenv('SGX_CERTIFICATES_FOLDER')
SKALE_BASE_DIR = os.getenv('SKALE_BASE_DIR')
TRANSACTION_MANAGER_IMAGE = os.getenv('TRANSACTION_MANAGER_IMAGE')
NODES_AMOUNT = int(os.getenv('NODES_AMOUNT') or 0)
ETH_AMOUNT = int(os.getenv('ETH_AMOUNT') or 0)
SCHAIN_TYPE = int(os.getenv('SCHAIN_TYPE') or 0)
SCHAINS_AMOUNT = int(os.getenv('SCHAINS_AMOUNT') or 0)

print('ENDPOINT: ', ENDPOINT)
print('SGX_SERVER_URL: ', SGX_SERVER_URL)
print('ABI_FILEPATH: ', TEST_ABI_FILEPATH)
print('NODES_AMOUNT: ', NODES_AMOUNT)
print('ETH_AMOUNT: ', ETH_AMOUNT)
print('SCHAINS_AMOUNT: ', SCHAINS_AMOUNT)
print('SCHAIN_TYPE: ', SCHAIN_TYPE)

TIMEOUT = 5


def generate_random_ip() -> str:
    return '.'.join('%s' % random.randint(0, 255) for i in range(4))


def generate_random_port() -> int:
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


class TxManager:
    INIT_WAIT_TIME = 30

    docker_client = docker.from_env()
    host = '127.0.0.1'
    gport = 10000

    def __init__(self, skale_dir: str) -> None:
        self.port = TxManager.gport
        TxManager.gport += 1
        self.name = f'tm-{self.port}'
        self.skale_dir = skale_dir
        self.keyname = TxManager.ensure_sgx_key(skale_dir)
        self.container = self.run()

    @classmethod
    def ensure_sgx_key(cls, skale_dir):
        node_config_path = Path(skale_dir).joinpath('node_data', 'node_config.json')
        if not node_config_path.exists():
            sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
            key_info = sgx.generate_key()
            with open(node_config_path, 'w') as config_file:
                json.dump({'sgx_key_name': key_info.name}, config_file)
            keyname = key_info.name
        else:
            with open(node_config_path) as config_file:
                data = json.load(config_file)
                keyname = data.get('sgx_key_name')
        return keyname

    def get_env(self) -> dict:
        sgx_certs_dirname = os.path.dirname(SGX_CERTIFICATES_FOLDER)
        return {
            'FLASK_APP_HOST': TxManager.host,
            'FLASK_APP_PORT': self.port,
            'FLASK_DEBUG_MODE': 'False',
            'ENDPOINT': ENDPOINT,
            'SGX_SERVER_URL': SGX_SERVER_URL,
            'SGX_CERTIFICATES_DIR_NAME': sgx_certs_dirname,
            'SKALE_DIR_HOST': self.skale_dir,
        }

    @property
    def url(self) -> str:
        return f'http://{TxManager.host}:{self.port}'

    def get_volumes(self, mode='Z') -> dict:
        return {
            os.path.abspath(self.skale_dir): {
                'bind': '/skale_vol',
                'mode': mode
            },
            os.path.abspath(os.path.join(self.skale_dir, 'node_data')): {
                'bind': '/skale_node_data',
                'mode': mode
            }
        }

    def get_rpc_wallet(self) -> RPCWallet:
        return RPCWallet(self.url)

    @property
    def container_cmd(self):
        return ' '.join([
            f'uwsgi --http 127.0.0.1:{self.port} --module main --callable app',
            '--hook-master-start "unix_signal:15 gracefully_kill_them_all"',
            '--die-on-term',
            '--need-app', '--master',
            '--http-timeout 200', '--single-interpreter',
            '--show-config'
        ])

    def run(self):
        return TxManager.docker_client.containers.run(
            image=TRANSACTION_MANAGER_IMAGE,
            name=self.name,
            network='host',
            tty=True,
            environment=self.get_env(),
            detach=True,
            volumes=self.get_volumes(),
            command=self.container_cmd
        )

    def stop(self) -> None:
        return self.container.stop()

    def rm(self, force: bool = False) -> None:
        return self.container.rm(force=force)


class Node:
    # Node should spin up transaction manager
    # How to create wallet without transaction manager
    # Save node info to skale_dir

    class AlreadyRegisteredError(Exception):
        pass

    base_path = os.path.join(BASE_PATH, 'nodes')

    def __init__(self, name: str, save: bool = True):
        self.name = name
        self.skale_dir = Node.ensure_skale_dir(name)
        self.id = Node.loads(name).get('id')
        self.tm = TxManager(self.skale_dir)
        self.wallet = self.tm.get_rpc_wallet()
        self.skale = Skale(ENDPOINT, TEST_ABI_FILEPATH, self.wallet)
        self.process = None
        if save:
            self.save()

    @classmethod
    def get_skale_dir_path(cls, node_name: str) -> Path:
        return Path(SKALE_BASE_DIR).joinpath(node_name)

    @classmethod
    def ensure_skale_dir(cls, node_name: str) -> Path:
        skale_dir_path = cls.get_skale_dir_path(node_name)
        abi_dir_path = Path(skale_dir_path).joinpath('contracts_info')
        abi_dir_path.mkdir(parents=True, exist_ok=True)
        copyfile(TEST_ABI_FILEPATH, abi_dir_path.joinpath('manager.json'))
        for dirname in ('log', 'sgx_certs', 'schains'):
            Path(skale_dir_path).joinpath('node_data', dirname).mkdir(
                exist_ok=True, parents=True
            )
        return skale_dir_path

    @classmethod
    def get_node_config_path(cls, skale_dir):
        return Path(skale_dir).joinpath('node_data', 'node_config.json')

    def join(self) -> None:
        self.process.join()

    def run_dkg_for_node_schains(self, schains: list) -> None:
        schain_config_pathes = [
            Path(self.skale_dir).joinpath('node_data', 'schains', schain)
            for schain in schains
        ]
        for path in schain_config_pathes:
            path.mkdir(parents=True, exist_ok=True)

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
                    self.id,
                    self.tm.keyname,
                    node_data_path=os.path.join(self.skale_dir, 'node_data')
                )
                for skale, schain in zip(schain_skales, schains)
            ]
        for future in as_completed(futures):
            future.result()

        for path in schain_config_pathes:
            shutil.rmtree(path)

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
        self.process = Thread(
            target=self.run_dkg_for_node_schains,
            args=(schains,)
        )
        self.process.start()

    @classmethod
    def loads(cls, node_name: str) -> dict:
        skale_dir = cls.get_skale_dir_path(node_name)
        node_config_path = cls.get_node_config_path(skale_dir)
        if node_config_path.exists():
            with open(node_config_path) as node_config_file:
                return json.load(node_config_file)
        return {}

    @classmethod
    def is_registered(cls, name: str) -> bool:
        ids = root_skale.nodes.get_active_node_ids()
        names = {root_skale.nodes.get(id_)['name'] for id_ in ids}
        return name in names

    def save(self, filepath: str = None) -> None:
        if filepath:
            node_config_path = Path(filepath)
        else:
            node_config_path = Node.get_node_config_path(self.skale_dir)

        data = {}
        if node_config_path.exists():
            with open(node_config_path) as node_config_file:
                try:
                    data = json.load(node_config_file)
                except json.JSONDecodeError:
                    pass
        data.update(self.to_dict())
        with open(node_config_path, 'w') as node_config_file:
            json.dump(data, node_config_file)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'id': self.id
        }

    @property
    def address(self) -> str:
        return self.skale.wallet.address

    def register(self, save: bool = True) -> int:
        if self.id is not None:
            return
            # raise Node.AlreadyRegisteredError()
        if Node.is_registered(self.name):
            data = Node.loads(self.name)
            id_ = data['id']
        else:
            ip = generate_random_ip()
            port = 1000
            self.skale.manager.create_node(
                ip=ip,
                port=port,
                name=self.name
            )
            id_ = self.skale.nodes.node_name_to_index(self.name)
        self.id = id_
        self.save()
        return id_


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


def ensure_nodes(amount: int) -> list:
    return [Node(f'node-{i}') for i in range(amount)]


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


def register_nodes(nodes: list) -> None:
    for node in nodes:
        node.register()


def generate_random_name(len: int = 16) -> None:
    return ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=len))


def create_schains(amount: int) -> None:
    schain_names = []
    for i in range(amount):
        name = generate_random_name()
        schain_names.append(name)
        lifetime_seconds = 12 * 3600
        price_in_wei = root_skale.schains.get_schain_price(
            SCHAIN_TYPE, lifetime_seconds)
        root_skale.manager.create_schain(lifetime=lifetime_seconds,
                                         type_of_nodes=SCHAIN_TYPE,
                                         deposit=price_in_wei, name=name)

        time.sleep(TIMEOUT)
    return schain_names


def prepare() -> list:
    # TODO: Save info about nodes
    validators = ensure_validators(NODES_AMOUNT)
    enable_validators(validators)
    # wallets = generate_wallets(NODES_AMOUNT)
    nodes = ensure_nodes(NODES_AMOUNT)
    print(f'Waiting for tm containers initialization')
    time.sleep(TxManager.INIT_WAIT_TIME)
    wallets = [node.wallet for node in nodes]
    send_eth_to_addresses([w.address for w in wallets], ETH_AMOUNT)
    link_node_wallets_to_validators(wallets, validators)
    register_nodes(nodes)
    return nodes


def run_dkg_test(nodes: list) -> None:
    print('======== Starting dkg test =====================================')
    schain_names = create_schains(SCHAINS_AMOUNT)
    for node in nodes:
        print(f'Address {node.skale.wallet.address}')
        node.start_dkg()

    print(nodes)
    for node in nodes:
        node.join()

    for schain_name in schain_names:
        gid = root_skale.schains.name_to_id(schain_name)
        assert root_skale.dkg.is_last_dkg_successful(gid)


@contextmanager
def cleanup_schains() -> None:
    try:
        yield
    finally:
        cleanup_schains_from_contracts()


def cleanup_schains_from_contracts():
    schain_ids = root_skale.schains_internal.get_all_schains_ids()
    names = [root_skale.schains.get(sid)['name'] for sid in schain_ids]
    print(names)
    for name in names:
        root_skale.manager.delete_schain(name)


def cleanup_tm_containers():
    docker_client = docker.from_env()
    tm_containers = filter(
        lambda c: c.name.startswith('tm'),
        docker_client.containers.list()
    )
    for c in tm_containers:
        print(c.name)
        c.remove(force=True)


def cleanup_schain_configs():
    for node_data_path in Path(SKALE_BASE_DIR).glob('node-*'):
        schain_base_dir_path = node_data_path.joinpath('node_data', 'schains')
        for schain_config_path in schain_base_dir_path.iterdir():
            print(schain_config_path)
            shutil.rmtree(schain_config_path)


def main() -> None:
    # init_default_logger()
    init_admin_logger()
    cleanup_tm_containers()
    cleanup_schain_configs()
    nodes = prepare()
    with cleanup_schains():
        run_dkg_test(nodes)


if __name__ == '__main__':
    main()
