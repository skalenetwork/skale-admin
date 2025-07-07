import time
from typing import Dict, List


def get_current_nodes(config: Dict) -> List[dict]:
    if config is None:
        return []
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']

    current_timestamp = int(time.time())

    timestamps = schain_nodes_config.keys()
    needed_timestamp = None
    for timestamp in sorted(timestamps, key=int):
        if int(timestamp) > current_timestamp:
            needed_timestamp = timestamp
            break

    if needed_timestamp is None:
        needed_timestamp = max(timestamps)
    return schain_nodes_config[needed_timestamp]['group']


def get_node_ips_from_config(config: Dict) -> List[str]:
    group_data = get_current_nodes(config)
    if len(group_data) == 0:
        return []
    return [node_data['ip'] for node_data in group_data]
