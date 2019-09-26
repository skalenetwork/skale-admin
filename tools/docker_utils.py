import logging
import docker
import re
from functools import wraps

from docker import APIClient

from tools.configs.docker import DOCKER_USERNAME, DOCKER_PASSWORD

logger = logging.getLogger(__name__)


def format_containers(f):
    @wraps(f)
    def inner(*args, **kwargs):
        containers = f(*args, **kwargs)
        res = []
        for container in containers:
            res.append({
                'image': container.attrs['Config']['Image'],
                'name': re.sub('/', '', container.attrs['Name']),
                'state': container.attrs['State']
            })
        return res
    return inner


class DockerUtils():
    def __init__(self):
        self.client = self.init_docker_client()
        self.cli = self.init_docker_cli()

    def init_docker_client(self):
        docker_client = docker.from_env()
        docker_client.login(username=DOCKER_USERNAME, password=DOCKER_PASSWORD)
        return docker_client

    def init_docker_cli(self):
        return APIClient()

    def data_volume_exists(self, name):
        try:
            self.cli.inspect_volume(name)
            return True
        except docker.errors.NotFound:
            return False

    def create_data_volume(self, name, size=None):
        driver_opts = {'size': str(size)} if size else None
        logging.info(
            f'Creating volume, driver: convoy, size: {size}, name: {name}, driver_opts: {driver_opts}')
        volume = self.client.volumes.create(
            name=name,
            driver='convoy',
            driver_opts=driver_opts,
            labels={"schain": name}
        )
        return volume

    @format_containers
    def get_all_skale_containers(self, all=False):
        return self.client.containers.list(all=all, filters={'name': 'skale_*'})

    @format_containers
    def get_all_schain_containers(self, all=False):
        return self.client.containers.list(all=all, filters={'name': 'skale_schain_*'})