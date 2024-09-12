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

import io
import itertools
import logging
import multiprocessing
import os
import re
import time
from datetime import datetime
from functools import wraps
from typing import Dict, Optional

import docker
from docker import APIClient
from docker.client import DockerClient
from docker.models.containers import Container
from docker.models.volumes import Volume

from tools.configs import DOCKER_NODE_CONFIG_FILEPATH
from tools.configs.containers import (
    CONTAINER_NOT_FOUND,
    CREATED_STATUS,
    DEFAULT_DOCKER_HOST,
    DOCKER_DEFAULT_HEAD_LINES,
    DOCKER_DEFAULT_TAIL_LINES,
    DOCKER_DEFAULT_STOP_TIMEOUT,
    EXITED_STATUS,
    RUNNING_STATUS,
    CONTAINER_LOGS_SEPARATOR
)
from tools.configs.logs import REMOVED_CONTAINERS_FOLDER_PATH
from tools.helper import read_json


logger = logging.getLogger(__name__)

MAX_RETRIES = 12
CONTAINER_CREATION_TIMEOUT = 10


class ContainerCreationTimeoutError(Exception):
    pass


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
                'state': container.attrs['State'],
                'cpu_shares': container.attrs['HostConfig']['CpuShares'],
                'mem_limit': container.attrs['HostConfig']['Memory'],
                'swap_limit': container.attrs['HostConfig']['MemorySwap'],
                'swappiness': container.attrs['HostConfig']['MemorySwappiness']
            })
        return res

    return inner


def get_docker_group_id() -> int:
    return read_json(DOCKER_NODE_CONFIG_FILEPATH)['docker_group_id']


class DockerUtils:
    docker_lock = multiprocessing.Lock()

    def __init__(
        self,
        volume_driver: str = 'lvmpy',
        host: str = DEFAULT_DOCKER_HOST
    ) -> None:
        self.client = self.init_docker_client(host=host)
        self.cli = self.init_docker_cli(host=host)
        self.volume_driver = volume_driver

    def init_docker_client(
        self,
        host: str = DEFAULT_DOCKER_HOST
    ) -> DockerClient:
        logger.debug('Initing docker client with host %s', host)
        return docker.DockerClient(base_url=host)

    def init_docker_cli(
        self,
        host: str = DEFAULT_DOCKER_HOST
    ) -> APIClient:
        return APIClient(base_url=host)

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

    def get_all_skale_containers(self, all=False, format=False) -> list:
        return self.get_containers_info(all=all, name_filter='skale_*')

    def get_all_schain_containers(self, all=False, format=False) -> list:
        return self.get_containers_info(all=all, name_filter='skale_schain_*')

    @format_containers
    def get_containers_info(self, all=False, name_filter='*', format=False) -> list:
        return self.client.containers.list(all=all, filters={'name': name_filter})

    @format_containers
    def get_all_ima_containers(self, all=False, format=False) -> list:
        return self.client.containers.list(all=all, filters={'name': 'skale_ima_*'})

    def get_info(self, container_id: str, raise_not_found: bool = False) -> dict:
        container_info = {}
        try:
            container = self.client.containers.get(container_id)
            container_info['stats'] = container.stats(decode=True, stream=True)

            container_info['stats'] = self.cli.inspect_container(container.id)
            container_info['status'] = container.status
        except docker.errors.NotFound:
            if raise_not_found:
                raise
            logger.debug(
                f'Can not get info - no such container: {container_id}')
            container_info['status'] = CONTAINER_NOT_FOUND
        return container_info

    def is_container_running(self, container_id: str) -> bool:
        info = self.get_info(container_id)
        return info['status'] == RUNNING_STATUS

    def is_container_found(self, container_id: str) -> bool:
        info = self.get_info(container_id)
        return info['status'] != CONTAINER_NOT_FOUND

    def is_container_created(self, container_id: str) -> bool:
        info = self.get_info(container_id)
        return info['status'] == CREATED_STATUS

    def is_container_exited(self, container_id: str) -> bool:
        info = self.get_info(container_id)
        return info['status'] == EXITED_STATUS

    def container_exit_code(self, container_id: str) -> int:
        info = self.get_info(container_id)
        if info['status'] != CONTAINER_NOT_FOUND:
            return info['stats']['State']['ExitCode']
        else:
            return -1

    def get_vol(self, name: str) -> Volume:
        try:
            return self.client.volumes.get(name)
        except docker.errors.NotFound:
            logger.debug(f'Volume {name} does not exist')
            return None

    def rm_vol(self, name: str, retry_lvmpy_error: bool = True) -> None:
        logger.info(f'Going to remove volume {name}')
        if retry_lvmpy_error:
            timeouts = [2 ** power for power in range(MAX_RETRIES)]
        else:
            timeouts = [0]
        error = None
        for i, timeout in enumerate(timeouts):
            volume = self.get_vol(name)
            if volume is None:
                return
            try:
                logger.info(f'Removing volume attempt {i}')
                volume.remove(force=True)
            except Exception as err:
                error = err
                logger.error(
                    f'Removing volume returned {err}. Sleeping {timeout}s')
                time.sleep(timeout)
            else:
                error = None
                break
        if error:
            raise error
        else:
            logger.info(f'Volume {name} was successfuly removed')

    def safe_get_container(self, container_name: str):
        logger.info(f'Trying to get container: {container_name}')
        try:
            return self.client.containers.get(container_name)
        except docker.errors.APIError as e:
            logger.debug(e)
            logger.debug(f'No such container: {container_name}')

    def safe_rm(self, container_name: str, timeout=DOCKER_DEFAULT_STOP_TIMEOUT, **kwargs):
        """
        Saves docker container logs (last N lines) in the .skale/node_data/log/.removed_containers
        folder. Then stops and removes container with specified params.
        """
        container = self.safe_get_container(container_name)
        if not container:
            return
        logger.info(
            f'Stopping container: {container_name}, timeout: {timeout}')
        container.stop(timeout=timeout)
        self.backup_container_logs(container)
        logger.info(f'Removing container: {container_name}, kwargs: {kwargs}')
        container.remove(**kwargs)
        logger.info(f'Container removed: {container_name}')

    @classmethod
    def get_container_logs(
        cls,
        container: Container,
        head: int = DOCKER_DEFAULT_HEAD_LINES,
        tail: int = DOCKER_DEFAULT_TAIL_LINES
    ):
        tail_lines = container.logs(tail=tail)
        lines_number = len(io.BytesIO(tail_lines).readlines())
        head = min(lines_number, head)
        log_stream = container.logs(stream=True, follow=True)
        head_lines = b''.join(itertools.islice(log_stream, head))
        return head_lines, tail_lines

    def display_container_logs(
        self,
        container_name: Container,
        head: int = 100,
        tail: int = 200,
        to_logger: bool = True
    ) -> str:
        container = self.safe_get_container(container_name)
        if not container:
            return
        head_lines, tail_lines = DockerUtils.get_container_logs(
            container=container,
            head=head,
            tail=tail
        )
        pretext = f'container {container_name} logs: \n'
        logs = (head_lines + CONTAINER_LOGS_SEPARATOR + tail_lines).decode("utf-8")
        if to_logger:
            logger.info(pretext + logs)
        else:
            print(pretext + logs)
        return logs

    @classmethod
    def save_container_logs(
        cls,
        container: Container,
        log_filepath: str,
        head: int = DOCKER_DEFAULT_HEAD_LINES,
        tail: int = DOCKER_DEFAULT_TAIL_LINES
    ) -> None:
        head_lines, tail_lines = DockerUtils.get_container_logs(
            container=container,
            head=head,
            tail=tail
        )
        with open(log_filepath, 'wb') as out:
            out.write(head_lines)
            out.write(CONTAINER_LOGS_SEPARATOR)
            out.write(tail_lines)

    def backup_container_logs(
        self,
        container: Container,
        head: int = DOCKER_DEFAULT_HEAD_LINES,
        tail: int = DOCKER_DEFAULT_TAIL_LINES
    ) -> None:
        logger.info(f'Going to backup container logs: {container.name}')
        logs_backup_filepath = self.get_logs_backup_filepath(container)
        DockerUtils.save_container_logs(
            container,
            logs_backup_filepath,
            head=head,
            tail=tail
        )
        logger.info(
            f'Old container logs saved to {logs_backup_filepath}, '
            f'head {head}, tail: {tail}'
        )

    def get_logs_backup_filepath(self, container: Container) -> str:
        container_index = sum(1 for f in os.listdir(REMOVED_CONTAINERS_FOLDER_PATH)
                              if f.startswith(f'{container.name}-'))
        log_file_name = f'{container.name}-{container_index}.log'
        return os.path.join(REMOVED_CONTAINERS_FOLDER_PATH, log_file_name)

    def restart(
        self,
        container_name: str,
        timeout: int = DOCKER_DEFAULT_STOP_TIMEOUT,
        **kwargs
    ):
        logger.info(f'Restarting container: {container_name}')
        try:
            container = self.client.containers.get(container_name)
            res = container.restart(timeout=timeout, **kwargs)
            logger.info(f'Container restarted: {container_name}')
            return res
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def get_cmd(self, container_id: str) -> Dict:
        info = self.get_info(container_id)
        if info:
            return info['stats']['Config']['Cmd']
        return {}

    def get_container_created_ts(self, container_id: str) -> int:
        info = self.get_info(container_id)
        if info:
            iso_time = info['stats']['Created'].split('.')[0]
            return int(datetime.fromisoformat(iso_time).timestamp())
        else:
            return 0

    def get_vol_created_ts(self, name: str) -> int:
        vol = self.get_vol(name)
        if vol:
            iso_time = vol.attrs['CreatedAt'][:-1]
            return int(datetime.fromisoformat(iso_time).timestamp())
        else:
            return 0

    def restart_all_schains(
        self,
        timeout: int = DOCKER_DEFAULT_STOP_TIMEOUT
    ) -> None:
        containers = self.get_all_schain_containers()
        for container in containers:
            self.restart(container.name, timeout=timeout)

    def pull(self, name: str) -> None:
        with DockerUtils.docker_lock:
            repo, tag = name.split(':')
            self.client.images.pull(repository=repo, tag=tag)

    def pulled(self, name: str) -> bool:
        with DockerUtils.docker_lock:
            try:
                self.client.images.get(name)
            except docker.errors.NotFound:
                return False
            return True

    def rmi(self, name: str) -> None:
        with DockerUtils.docker_lock:
            self.client.images.remove(name)

    def get_container_image_name(self, name: str) -> Optional[str]:
        info = self.get_info(name)
        if info.get('status') == CONTAINER_NOT_FOUND:
            return None
        return info['stats']['Config']['Image']

    def get_container_env_value(self, container_name: str, env_option: str) -> Optional[str]:
        info = self.get_info(container_name, raise_not_found=True)
        env = info['stats']['Config']['Env']
        try:
            value = next(filter(lambda v: v.startswith(env_option), env))
        except StopIteration:
            return None
        return value.split('=')[1]

    def wait_for_container_creation(self, name: str, timeout=CONTAINER_CREATION_TIMEOUT):
        start_ts = time.time()
        while time.time() - start_ts < timeout and not self.is_container_exists(name):
            time.sleep(0.2)
        if not self.is_container_exists(name):
            raise ContainerCreationTimeoutError(f'{name} has not been created within {timeout}s')
