import logging

from core.schains.types import SchainTypes
from tools.helper import read_json
from tools.configs.resource_allocation import RESOURCE_ALLOCATION_FILEPATH
from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)
docker_utils = DockerUtils()


def init_data_volume(schain):
    schain_name = schain['name']

    if docker_utils.data_volume_exists(schain_name):
        logger.debug(f'Volume already exists: {schain_name}')
        return

    logger.info(f'Creating volume for schain: {schain_name}')
    option_name = get_allocation_option_name(schain)
    resource_allocation = get_resource_allocation_info()
    volume_size = resource_allocation['disk'][f'part_{option_name}']

    return docker_utils.create_data_volume(schain_name, volume_size)


def get_container_limits(schain):
    size = get_allocation_option_name(schain)
    cpu_limit = get_allocation_option('cpu', size)
    nanocpu_limit = cpu_to_nanocpu(cpu_limit)
    return nanocpu_limit, get_allocation_option('mem', size)


def cpu_to_nanocpu(cpu_limit):
    return int(cpu_limit * 10 ** 9)


def get_allocation_option(metric, size):
    resource_allocation = get_resource_allocation_info()
    return resource_allocation[metric][f'part_{size}']


def get_allocation_option_name(schain):
    part_of_node = int(schain['partOfNode'])
    return SchainTypes(part_of_node).name


def get_resource_allocation_info():
    return read_json(RESOURCE_ALLOCATION_FILEPATH)
