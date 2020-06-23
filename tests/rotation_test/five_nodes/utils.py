import os

from skale.manager_client import spawn_skale_lib

from core.node import Node
from core.schains.runner import get_image_name
from core.schains.volume import get_resource_allocation_info
from tests.conftest import init_skale
from tests.dkg_test.main_test import run_dkg_all
from tests.rotation_test.three_nodes.utils import set_up_nodes, NodeConfigMock
from tests.utils import generate_random_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils
from skale.dataclasses.skaled_ports import SkaledPorts


dutils = DockerUtils()

node_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)))
base_port = 10000
local_ip = '127.0.0.1'


def register_node(skale, wallet, id):
    skale.wallet = wallet
    ip, public_ip, port, name = (local_ip, local_ip, base_port*id, f'node{id}')
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)
    node_id = skale.nodes.node_name_to_index(name)
    return {
        'node': skale.nodes.get_by_name(name),
        'node_id': node_id,
        'wallet': wallet
    }


def register_nodes(skale, wallets, start_id=1):
    base_wallet = skale.wallet
    nodes = [
        register_node(skale, wallet, node_id)
        for wallet, node_id in enumerate(wallets, start_id)
    ]
    skale.wallet = base_wallet
    return nodes


def create_schain(skale, name):
    lifetime = 3600
    nodes_type = 5
    price_in_wei = skale.schains.get_schain_price(
        nodes_type, lifetime)
    skale.manager.create_schain(lifetime, nodes_type, price_in_wei, name, wait_for=True)


def set_up_schain_on_contracts(skale):
    nodes_data = set_up_nodes(skale, 4)
    print('nodes:', skale.nodes.get_active_node_ids())
    schain_name = generate_random_name()
    create_schain(skale, schain_name)
    run_dkg_all(skale, schain_name, nodes_data)
    nodes_data.append(set_up_nodes(skale, 1)[0])

    nodes = []
    for node in nodes_data:
        skale_lib = spawn_skale_lib(skale)
        skale_lib.wallet = node['wallet']
        config = NodeConfigMock()
        config.id = node['node_id']
        nodes.append(Node(skale_lib, config))

    return nodes, schain_name


def get_args(node_id):
    volume_host_path = os.path.join(node_dir, f'node{node_id}')
    node_base_port = node_id*base_port
    opts = (
        f'--config /schain_data/config.json '
        f'-d /schain_data/data_dir '
        f'--ipcpath /schain_data/data_dir '
        f'--http-port {node_base_port + SkaledPorts.HTTP_JSON.value} '
        f'--https-port {node_base_port + SkaledPorts.HTTPS_JSON.value} '
        f'--ws-port {node_base_port + SkaledPorts.WS_JSON.value} '
        f'--wss-port {node_base_port + SkaledPorts.WSS_JSON.value} '
        f'-v 4 '
        f'--web3-trace '
        f'--enable-debug-behavior-apis '
        f'--aa no '
    )
    run_args = dict()
    run_args['network_mode'] = 'host'
    run_args["cap_add"] = [
        "SYS_PTRACE",
        "SYS_ADMIN"
    ]
    run_args['environment'] = {
        'OPTIONS': opts,
        'DATA_DIR': '/schain_data/data_dir',
        'NO_NTP_CHECK': 1
    }
    run_args['volumes'] = {
        volume_host_path: {
            'bind': '/schain_data',
            "mode": "rw"
        },
        f'node{node_id}': {
            'bind': '/schain_data/data_dir',
            'mode': 'rw'
        }
    }
    return run_args


def run_schain_containers(nodes_count=4):
    image = get_image_name(SCHAIN_CONTAINER)

    for i in range(1, nodes_count + 1):
        resource_allocation = get_resource_allocation_info()
        volume_size = resource_allocation['disk']['part_small']
        dutils.create_data_volume(name=f'node{i}', size=volume_size)
        run_args = get_args(i)
        dutils.client.containers.run(image, name=f'node{i}', detach=True, **run_args)


if __name__ == "__main__":
    set_up_schain_on_contracts(init_skale())
    run_schain_containers()
