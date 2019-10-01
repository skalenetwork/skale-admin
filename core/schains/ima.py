from core.schains.helper import get_schain_data_dir, get_schain_config_filepath, \
    get_schain_config, get_schain_dir_path, get_schain_proxy_file_path
from core.schains.config import get_schain_ports

from tools.configs.mta import MTA_ENDPOINT
from tools.config import LOCAL_WALLET_FILEPATH, MAINNET_PROXY_PATH


def get_node_http_endpoint(node_info, schain_name):
    ports = get_schain_ports(schain_name)
    return f'http://{node_info["bindIP"]}:{ports["http"]}'


def get_ima_env(schain_name):
    data_dir = get_schain_data_dir(schain_name)
    config_filepath = get_schain_config_filepath(schain_name)

    schain_config = get_schain_config(schain_name)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    schain_nodes = schain_config["skaleConfig"]["sChain"]

    schain_index = None
    for node in schain_nodes['nodes']:
        if node['nodeID'] == node_info['nodeID']:
            schain_index = node['schainIndex']
            break

    if not schain_index:
        schain_index = 0

    return {
        "SCHAIN_ID": schain_name,
        "CONFIG_FILE": config_filepath,
        "DATA_DIR": data_dir,
        "SCHAIN_DIR": get_schain_dir_path(schain_name),

        "LOCAL_WALLET_PATH": LOCAL_WALLET_FILEPATH,
        "MAINNET_PROXY_PATH": MAINNET_PROXY_PATH,
        "SCHAIN_PROXY_PATH": get_schain_proxy_file_path(schain_name),

        "SCHAIN_RPC_URL": get_node_http_endpoint(node_info, schain_name),
        "MAINNET_RPC_URL": MTA_ENDPOINT,

        "NODE_NUMBER": schain_index,
        "NODES_COUNT": len(schain_nodes['nodes'])
    }
