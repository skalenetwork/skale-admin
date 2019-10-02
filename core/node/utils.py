import logging

logger = logging.getLogger(__name__)


def get_node_id(config):
    try:
        return config['node_id']
    except KeyError:
        logger.info('get_node_id: No node installed on this machine.')
        return None
