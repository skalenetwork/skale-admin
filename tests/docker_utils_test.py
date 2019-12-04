import os

import docker
import pytest
from skale.utils.web3_utils import wait_receipt, check_receipt

from tools.docker_utils import DockerUtils
from core.schains.runner import run_schain_container


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
TEST_SKALE_DATA_DIR = os.path.join(DIR_PATH, 'skale-data')
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.path.join(DIR_PATH, 'test_abi.json')


SCHAIN_NAME = 'test'


@pytest.fixture
def client():
    return DockerUtils()


def manager_node_schains_init(skale_inst):
    # Create first node
    res = skale_inst.manager.create_node('1.1.1.2', 8081, 'node1', '4.4.3.3')
    receipt = wait_receipt(skale_inst.web3, res['tx'])
    check_receipt(receipt)

    # Create second node
    res = skale_inst.manager.create_node('2.2.5.5', 8082, 'node2', '4.4.5.5')
    receipt = wait_receipt(skale_inst.web3, res['tx'])
    check_receipt(receipt)

    # Create schain
    price_in_wei = skale_inst.schains.get_schain_price(4, 3600)
    res = skale_inst.manager.create_schain(3600, 4, price_in_wei, SCHAIN_NAME)
    receipt = wait_receipt(skale_inst.web3, res['tx'])
    check_receipt(receipt)


def test_run_schain_container(client):
    env = {
        "SSL_KEY_PATH": 'NULL',
        "SSL_CERT_PATH": 'NULL',
        "HTTP_RPC_PORT": 10002,
        "HTTPS_RPC_PORT": 10007,
        "WS_RPC_PORT": 10003,
        "WSS_RPC_PORT": 10008,

        "SCHAIN_ID": SCHAIN_NAME,
        "CONFIG_FILE": os.path.join(TEST_SKALE_DATA_DIR, 'schain_config.json'),
        "DATA_DIR": '/data_dir'
    }

    schain_data = {'name': SCHAIN_NAME,
                   'owner': '0x1213123091i230923123213123',
                   'indexInOwnerList': 0, 'partOfNode': 0,
                   'lifetime': 3600, 'startDate': 1575448438,
                   'deposit': 1000000000000000000, 'index': 0,
                   'active': True}

    # Run schain container
    run_schain_container(schain_data, env)

    # Perform container checks
    assert client.data_volume_exists(SCHAIN_NAME)

    containers = client.get_all_schain_containers()
    assert len(containers) == 1
    containers = client.get_all_skale_containers()
    assert len(containers) == 1

    info = client.get_info(containers[0].id)
    assert 'stats' in info
    assert info['status'] == 'running'
    assert client.container_running(info)

    # Remove container and volume
    assert containers[0].name
    client.safe_rm(containers[0].name, force=True)
    client.rm_vol(SCHAIN_NAME)


def test_not_existed_docker_objects(client):
    # Not existed volume
    assert not client.data_volume_exists('random_name')
    with pytest.raises(docker.errors.NotFound):
        client.rm_vol('random_name')

    # Not existed container
    info = client.get_info('random_id')
    assert info['status'] == 'not_found'
    assert client.to_start_container(info)
    client.safe_rm('random_name')
