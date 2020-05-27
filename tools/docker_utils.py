#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import docker
import re
from functools import wraps

from docker import APIClient

from tools.configs.containers import CONTAINER_NOT_FOUND, RUNNING_STATUS

logger = logging.getLogger(__name__)


def format_containers(f):
    @wraps(f)
    def inner(*args, **kwargs):
        format = kwargs.get('format', None)
        containers = f(*args, **kwargs)
        if not format:
            return containers
        res = []
        for container in containers:
            res.append({
                'image': container.attrs['Config']['Image'],
                'name': re.sub('/', '', container.attrs['Name']),
                'state': container.attrs['State']
            })
        return res

    return inner


class DockerUtils:
    def __init__(self, volume_driver='lvmpy'):
        self.client = self.init_docker_client()
        self.cli = self.init_docker_cli()
        self.volume_driver = volume_driver

    def init_docker_client(self):
        return docker.from_env()

    def init_docker_cli(self):
        return APIClient()

    def data_volume_exists(self, name):
        try:
            self.cli.inspect_volume(name)
            return True
        except docker.errors.NotFound:
            return False

    def create_data_volume(self, name, size=None):
        driver_opts = None
        if self.volume_driver != 'local' and size:
            driver_opts = {'size': str(size)}
        logging.info(
            f'Creating volume - size: {size}, name: {name}, driver_opts: {driver_opts}')
        volume = self.client.volumes.create(
            name=name,
            driver=self.volume_driver,
            driver_opts=driver_opts,
            labels={"schain": name}
        )
        return volume

    @format_containers
    def get_all_skale_containers(self, all=False, format=False):
        return self.client.containers.list(all=all, filters={'name': 'skale_*'})

    @format_containers
    def get_all_schain_containers(self, all=False, format=False):
        return self.client.containers.list(all=all, filters={'name': 'skale_schain_*'})

    def get_info(self, container_id):
        container_info = {}
        try:
            container = self.client.containers.get(container_id)
            container_info['stats'] = container.stats(decode=True, stream=True)

            container_info['stats'] = self.cli.inspect_container(container.id)
            container_info['status'] = container.status
        except docker.errors.NotFound:
            logger.warning(
                f'Can not get info - no such container: {container_id}')
            container_info['status'] = CONTAINER_NOT_FOUND
        return container_info

    def container_running(self, container_info):
        return container_info['status'] == RUNNING_STATUS

    def to_start_container(self, container_info):
        return container_info['status'] == CONTAINER_NOT_FOUND

    def container_exited(self, container_info):
        return container_info['stats']['State']['ExitCode'] == 0

    def rm_vol(self, name):
        volume = self.client.volumes.get(name)
        if volume:
            logger.warning(f'Going to remove volume {name}')
            volume.remove(force=True)

    def safe_rm(self, container_name, **kwargs):
        logger.info(f'Removing container: {container_name}')
        try:
            container = self.client.containers.get(container_name)
            res = container.remove(**kwargs)
            logger.info(f'Container removed: {container_name}')
            return res
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def restart(self, container_name, **kwargs):
        logger.info(f'Restarting container: {container_name}')
        try:
            container = self.client.containers.get(container_name)
            res = container.restart(**kwargs)
            logger.info(f'Container restarted: {container_name}')
            return res
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def restart_all_schains(self):
        containers = self.get_all_schain_containers()
        for container in containers:
            self.restart(container.name)
