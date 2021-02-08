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

import os
import logging
import re
import time
from functools import wraps

import docker
from docker import APIClient
from docker.client import DockerClient
from docker.models.containers import Container
from docker.models.volumes import Volume

from tools.configs.containers import (CONTAINER_NOT_FOUND, RUNNING_STATUS, EXITED_STATUS,
                                      DOCKER_DEFAULT_TAIL_LINES, DOCKER_DEFAULT_STOP_TIMEOUT)
from tools.configs.logs import REMOVED_CONTAINERS_FOLDER_PATH

logger = logging.getLogger(__name__)

MAX_RETRIES = 12


def format_containers(f):
    @wraps(f)
    def inner(*args, **kwargs) -> list:
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
    def __init__(self, volume_driver: str = 'lvmpy') -> None:
        self.client = self.init_docker_client()
        self.cli = self.init_docker_cli()
        self.volume_driver = volume_driver

    def init_docker_client(self) -> DockerClient:
        return docker.from_env()

    def init_docker_cli(self) -> APIClient:
        return APIClient()

    def is_data_volume_exists(self, name: str) -> bool:
        try:
            self.cli.inspect_volume(name)
        except docker.errors.NotFound:
            return False
        return True

    def is_container_exists(self, name: str) -> bool:
        try:
            self.client.containers.get(name)
        except docker.errors.NotFound:
            return False
        return True

    def run_container(self, image_name: str, name: str,
                      *args, **kwargs) -> Container:
        return self.client.containers.run(image_name, name=name, detach=True,
                                          *args, **kwargs)

    def create_data_volume(self, name: str, size: int = None) -> Volume:
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
    def get_all_skale_containers(self, all=False, format=False) -> list:
        return self.client.containers.list(all=all, filters={'name': 'skale_*'})

    @format_containers
    def get_all_schain_containers(self, all=False, format=False) -> list:
        return self.client.containers.list(all=all, filters={'name': 'skale_schain_*'})

    @format_containers
    def get_all_ima_containers(self, all=False, format=False) -> list:
        return self.client.containers.list(all=all, filters={'name': 'skale_ima_*'})

    def get_info(self, container_id: str) -> dict:
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

    def container_running(self, container_info: dict) -> bool:
        return container_info['status'] == RUNNING_STATUS

    def container_found(self, container_info: dict) -> bool:
        return container_info['status'] != CONTAINER_NOT_FOUND

    def is_container_exited(self, container_info: dict) -> bool:
        return container_info['status'] == EXITED_STATUS

    def is_container_exited_with_zero(self, container_info: dict) -> bool:
        return self.is_container_exited(container_info) and \
            container_info['stats']['State']['ExitCode'] == 0

    def container_exit_code(self, container_info: dict) -> int:
        if self.container_found(container_info):
            return container_info['stats']['State']['ExitCode']
        else:
            return -1

    def get_vol(self, name: str) -> Volume:
        try:
            return self.client.volumes.get(name)
        except docker.errors.NotFound:
            logger.warning(f'Volume {name} is not exist')
            return None

    def rm_vol(self, name: str, retry_lvmpy_error: bool = True) -> None:
        volume = self.get_vol(name)
        if volume is None:
            return
        logger.info(f'Going to remove volume {name}')
        if retry_lvmpy_error:
            timeouts = [2 ** power for power in range(MAX_RETRIES)]
        else:
            timeouts = [0]
        error = None
        for i, timeout in enumerate(timeouts):
            try:
                logger.info(f'Removing volume attempt {i}')
                volume.remove(force=True)
            except Exception as err:
                error = err
                logger.error(
                    f'Removing volume failed with {err}. Sleeping {timeout}s')
                time.sleep(timeout)
            else:
                error = None
                break
        if error:
            raise error

    def safe_get_container(self, container_name: str):
        logger.info(f'Trying to get container: {container_name}')
        try:
            return self.client.containers.get(container_name)
        except docker.errors.APIError as e:
            logger.warning(e)
            logger.warning(f'No such container: {container_name}')

    def safe_rm(self, container_name: str, stop_timeout=DOCKER_DEFAULT_STOP_TIMEOUT, **kwargs):
        """
        Saves docker container logs (last N lines) in the .skale/node_data/log/.removed_containers
        folder. Then stops and removes container with specified params.
        """
        container = self.safe_get_container(container_name)
        if not container:
            return
        self.backup_container_logs(container)
        logger.info(f'Stopping container: {container_name}, timeout: {stop_timeout}')
        container.stop(timeout=stop_timeout)
        logger.info(f'Removing container: {container_name}, kwargs: {kwargs}')
        container.remove(**kwargs)
        logger.info(f'Container removed: {container_name}')

    def backup_container_logs(self, container: Container, tail=DOCKER_DEFAULT_TAIL_LINES) -> None:
        logger.info(f'Going to backup container logs: {container.name}')
        logs_backup_filepath = self.get_logs_backup_filepath(container)
        with open(logs_backup_filepath, "wb") as out:
            out.write(container.logs(tail=tail))
        logger.info(f'Old container logs saved to {logs_backup_filepath}, tail: {tail}')

    def get_logs_backup_filepath(self, container: Container) -> str:
        container_index = sum(1 for f in os.listdir(REMOVED_CONTAINERS_FOLDER_PATH)
                              if f.startswith(f'{container.name}-'))
        log_file_name = f'{container.name}-{container_index}.log'
        return os.path.join(REMOVED_CONTAINERS_FOLDER_PATH, log_file_name)

    def restart(self, container_name: str, **kwargs):
        logger.info(f'Restarting container: {container_name}')
        try:
            container = self.client.containers.get(container_name)
            res = container.restart(**kwargs)
            logger.info(f'Container restarted: {container_name}')
            return res
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def restart_all_schains(self) -> None:
        containers = self.get_all_schain_containers()
        for container in containers:
            self.restart(container.name)
