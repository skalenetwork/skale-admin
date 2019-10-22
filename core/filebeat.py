import logging
from tools.helper import process_template
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

from tools.configs.filebeat import (FILEBEAT_TEMPLATE_PATH, FILEBEAT_CONTAINER_NAME,
                                    FILEBEAT_CONFIG_PATH)

dutils = DockerUtils()
logger = logging.getLogger(__name__)


def run_filebeat_service(node_ip, node_id, skale):
    contract_address = skale.manager.address
    template_data = {
        'ip': node_ip,
        'id': node_id,
        'contract_address': contract_address
    }
    logger.info(arguments_list_string(
        {'Node ID': node_id, 'Node IP': node_ip, 'Manager contract address': contract_address},
        'Processing Filebeat template'))
    process_template(FILEBEAT_TEMPLATE_PATH, FILEBEAT_CONFIG_PATH, template_data)
    filebeat_container = dutils.client.containers.get(FILEBEAT_CONTAINER_NAME)
    filebeat_container.restart()
