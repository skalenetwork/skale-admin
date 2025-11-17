import json
import os
import pathlib

import docker
import pytest

from core.chain.status import SkaledStatus, init_skaled_status
from core.config.schain.directory import skaled_status_filepath
from core.schains.cleaner import remove_schain_volume, remove_skaled_container
from tests.conftest import rm_schain_dir
from tests.utils import generate_skaled_status_file
from tools.configs.containers import CONTAINERS_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.docker_utils import DockerUtils


@pytest.fixture(scope='session')
def images():
    dclient = docker.from_env()
    cinfo = {}
    with open(CONTAINERS_FILEPATH, 'r') as cf:
        cinfo = json.load(cf)
    schain_image = '{}/{}'.format(cinfo['schain']['name'], cinfo['schain']['version'])
    ima_image = '{}/{}'.format(cinfo['ima']['name'], cinfo['ima']['version'])
    dclient.images.pull(schain_image)
    dclient.images.pull(ima_image)


@pytest.fixture
def skaled_status(_schain_name):
    generate_skaled_status_file(_schain_name)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_downloading_snapshot(_schain_name):
    generate_skaled_status_file(_schain_name, snapshot_downloader=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_exit_time_reached(_schain_name):
    generate_skaled_status_file(_schain_name, exit_time_reached=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_repair(_schain_name):
    generate_skaled_status_file(_schain_name, clear_data_dir=True, start_from_snapshot=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_reload(_schain_name):
    generate_skaled_status_file(_schain_name, start_again=True)
    try:
        yield init_skaled_status(_schain_name)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def skaled_status_broken_file(_schain_name):
    schain_dir_path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(schain_dir_path).mkdir(parents=True, exist_ok=True)
    status_filepath = skaled_status_filepath(_schain_name)
    with open(status_filepath, 'w') as text_file:
        text_file.write('abcd')
    try:
        yield SkaledStatus(status_filepath)
    finally:
        rm_schain_dir(_schain_name)


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local', host='unix://var/run/docker.sock')


@pytest.fixture
def skaled_mock_image(scope='module'):
    dutils = DockerUtils(volume_driver='local', host='unix://var/run/docker.sock')
    name = 'skaled-mock'
    dutils.client.images.build(tag=name, rm=True, nocache=True, path='tests/skaled-mock')
    yield name
    dutils.client.images.remove(name, force=True)


@pytest.fixture
def clean_docker(dutils, cleanup_schain_containers, cleanup_ima_containers):
    pass


@pytest.fixture
def cleanup_schain_containers(dutils):
    try:
        yield
    finally:
        containers = dutils.get_all_schain_containers(all=True)
        for container in containers:
            dutils.safe_rm(container.name, force=True)
            dutils.safe_rm(container.name.replace('schain', 'ima'), force=True)


@pytest.fixture
def cleanup_ima_containers(dutils):
    try:
        yield
    finally:
        containers = dutils.get_all_ima_containers(all=True)
        for container in containers:
            dutils.safe_rm(container.name, force=True)


@pytest.fixture
def cleanup_container(schain_config, dutils):
    try:
        yield
    finally:
        schain_name = schain_config['skaleConfig']['sChain']['schainName']
        cleanup_schain_container(schain_name, dutils)


def cleanup_schain_container(schain_name: str, dutils: DockerUtils):
    remove_skaled_container(schain_name, dutils)
    remove_schain_volume(schain_name, dutils)
