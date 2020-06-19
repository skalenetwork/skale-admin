import os

from core.schains.runner import get_image_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils
from skale.dataclasses.skaled_ports import SkaledPorts


NODES = ['node1', 'node2', 'node3', 'node4']
dutils = DockerUtils()

node_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)))
base_port = 10000


def set_up_nodes():
    pass


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
    run_args['environment'] = {
        'OPTIONS': opts,
        'DATA_DIR': '/schain_data/data_dir',
        'NO_NTP_CHECK': 1
    }
    run_args['volumes'] = {
        volume_host_path: {
            'bind': '/schain_data',
            "mode": "rw"
        }
    }
    return run_args


def run_schain_containers(nodes_count=4):
    image = get_image_name(SCHAIN_CONTAINER)

    for i in range(1, nodes_count + 1):
        run_args = get_args(i)
        dutils.client.containers.run(image, name=f'node{i}', detach=True, **run_args)


if __name__ == "__main__":
    run_schain_containers()
