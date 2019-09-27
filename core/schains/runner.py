from tools.config import CONTAINERS_FILEPATH, CONTAINER_NAME_PREFIX
from tools.helper import read_json

containers_info = read_json(CONTAINERS_FILEPATH)

SCHAIN_CONTAINER = 'schain'
IMA_CONTAINER = 'mta'

SCHAIN_IMAGE_NAME = construct_image_name('schain')
IMA_IMAGE_NAME = construct_image_name('ima')

def construct_image_name(name):
    container_info = containers_info[name]
    return f'{container_info["name"]}:{container_info["version"]}'


def construct_ima_container_name(schain_name):
    return f"{CONTAINER_NAME_PREFIX}{IMA_CONTAINER}_{schain_name}"


def construct_schain_container_name(schain_name):
    return f"{CONTAINER_NAME_PREFIX}{SCHAIN_CONTAINER}_{schain_name}"


def construct_container_name(config_container_name):
    return f"{CONTAINER_NAME_PREFIX}{config_container_name}"





def run_schain_container():



    # pass to docker utils
    pass

def run_ima_container():
    pass

    # pass to docker utils