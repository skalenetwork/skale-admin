#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import docker
import logging
import copy
from docker import APIClient
from docker.types import LogConfig

from tools.config_storage import ConfigStorage
from tools.config import DOCKER_USERNAME, DOCKER_PASSWORD, CONTAINER_NAME_PREFIX

docker_client = docker.from_env()

if DOCKER_USERNAME and DOCKER_PASSWORD:
    # todo: add warning!
    docker_client.login(username=DOCKER_USERNAME, password=DOCKER_PASSWORD)
else:
    raise Exception('You should set DOCKER_USERNAME and DOCKER_PASSWORD')

cli = APIClient()

logger = logging.getLogger(__name__)

CONTAINER_NOT_FOUND = 'not_found'
EXITED_STATUS = 'exited'
RUNNING_STATUS = 'running'

SCHAIN_CONTAINER = 'schain'
MTA_CONTAINER = 'mta'
ERROR_STATUSES = ['not_found', 'stopped', 'exited']


def get_docker_client():
    return docker_client


def get_docker_cli():
    return cli


class DockerManager():
    def __init__(self, config_path):
        self.config = ConfigStorage(config_path)

    def construct_image_fullname(self, name, version):
        return f"{name}:{version}"

    def construct_mta_container_name(self, schain_id):
        return f"{CONTAINER_NAME_PREFIX}{MTA_CONTAINER}_{schain_id}"

    def construct_schain_container_name(self, schain_id):
        return f"{CONTAINER_NAME_PREFIX}{SCHAIN_CONTAINER}_{schain_id}"

    def construct_container_name(self, config_container_name):
        return f"{CONTAINER_NAME_PREFIX}{config_container_name}"

    def get_info_by_config_name(self, name):
        return self.get_info(self.construct_container_name(name))

    def get_info(self, container_id):
        container_info = {}
        try:
            container = docker_client.containers.get(container_id)
            container_info['stats'] = container.stats(decode=True, stream=True)

            container_info['stats'] = cli.inspect_container(container.id)
            container_info['status'] = container.status
        except docker.errors.NotFound:
            logger.warning(f'Can not get info - no such container: {container_id}')
            container_info['status'] = CONTAINER_NOT_FOUND
        return container_info

    def run_container(self, image_name, container_name, run_args, volume_config=None,
                      cpu_limit=None, mem_limit=None):
        local_run_args = copy.deepcopy(run_args)

        if 'ulimits_list' in local_run_args:
            ulimits = []
            for ulimit in local_run_args['ulimits_list']:
                limit = docker.types.Ulimit(name=ulimit['name'], soft=ulimit['soft'],
                                            hard=ulimit['hard'])
                ulimits.append(limit)

            local_run_args['ulimits'] = ulimits
            del local_run_args['ulimits_list']

        lc = LogConfig(type=LogConfig.types.JSON, config={
            'max-size': '250m',
            'max-file': '5'
        })
        local_run_args['log_config'] = lc

        if volume_config:
            if local_run_args.get('volumes'):
                local_run_args['volumes'].update(volume_config)
            else:
                local_run_args['volumes'] = volume_config
        if cpu_limit:
            local_run_args['nano_cpus'] = cpu_limit
        if mem_limit:
            local_run_args['mem_limit'] = mem_limit

        logger.info(f'run_args: {local_run_args}')
        container_info = docker_client.containers.run(image_name, detach=True, name=container_name,
                                                      **local_run_args)
        logger.info(f'{image_name} container id: {container_info.id}')
        return container_info

    def run(self, name, container_name=None, volumes_config=None, custom_args={}):
        container_config = self.config[name]
        logger.info(f'Running container: {name}')

        run_args = container_config['args']
        run_args.update(custom_args)

        if not container_name:
            container_name = CONTAINER_NAME_PREFIX + name

        image_name = self.construct_image_fullname(container_config['name'],
                                                   container_config['version'])
        return self.run_container(image_name, container_name, run_args, volumes_config)

    def run_schain(self, schain_id, volume_mount_path, runtime_args=None, cpu_limit=None,
                   mem_limit=None):
        container_config = self.config[SCHAIN_CONTAINER]
        logger.info(f'Running container: {SCHAIN_CONTAINER}')

        run_args = container_config['args']
        if runtime_args:
            run_args.update(runtime_args)

        container_name = self.construct_schain_container_name(schain_id)
        image_name = self.construct_image_fullname(container_config['name'],
                                                   container_config['version'])

        volume_config = self.get_volume_config(schain_id, volume_mount_path)
        return self.run_container(image_name, container_name, run_args, volume_config, cpu_limit,
                                  mem_limit)

    def safe_stop(self, container_name):
        logger.info(f'Stopping container: {container_name}')
        try:
            container = docker_client.containers.get(container_name)
            container.stop()
            logger.info(f'Container stopped: {container_name}')
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def safe_rm(self, container_name, **kwargs):
        logger.info(f'Removing container: {container_name}')
        try:
            container = docker_client.containers.get(container_name)
            res = container.remove(**kwargs)
            logger.info(f'Container removed: {container_name}')
            return res
        except docker.errors.APIError:
            logger.error(f'No such container: {container_name}')

    def to_start_container(self, container_info):
        return container_info['status'] == CONTAINER_NOT_FOUND

    def container_running(self, container_info):
        return container_info['status'] == RUNNING_STATUS

    def create_data_volume(self, name, size=None):
        driver_opts = {'size': str(size)} if size else None
        logging.info(
            f'Creating volume, driver: convoy, size: {size}, name: {name}, driver_opts: {driver_opts}')
        volume = docker_client.volumes.create(
            name=name,
            driver='convoy',
            driver_opts=driver_opts,
            labels={"schain": name}
        )
        return volume

    def data_volume_exists(self, name):
        try:
            cli.inspect_volume(name)
            return True
        except docker.errors.NotFound:
            return False

    def get_volume_config(self, name, mount_path):
        return {f'{name}': {'bind': mount_path, 'mode': 'rw'}}

    def rm_vol(self, name):
        volume = docker_client.volumes.get(name)
        if volume:
            logger.warning(f'Going to remove volume {name}')
            volume.remove(force=True)