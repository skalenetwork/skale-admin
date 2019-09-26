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

import re
from tools.dockertools import DockerManager
from tools.config import CONTAINERS_FILEPATH
from core.schains.helper import get_healthcheck_value, get_healthcheck_name

SCHAIN_CONTAINER = 'schain'


class Containers():
    def __init__(self, skale, config, run_mode=None):
        self.docker_manager = DockerManager(CONTAINERS_FILEPATH)
        self.skale = skale
        self.config = config
        self.run_mode = run_mode

    def get_all_schains(self, all):
        containers = self.docker_manager.get_all_schain_containers(all)
        return self.format_containers(containers)

    def get_all_skale_containers(self, all):
        containers = self.docker_manager.get_all_skale_containers(all)
        return self.format_containers(containers)

    def format_containers(self, containers):
        res = []
        for container in containers:
            res.append({
                'image': container.attrs['Config']['Image'],
                'name': re.sub('/', '', container.attrs['Name']),
                'state': container.attrs['State']
            })
        return res


    def get_all(self):
        containers_info = []
        containers_list = self.docker_manager.config.config.copy()
        containers_list.pop(SCHAIN_CONTAINER, None)

        for name in containers_list:
            version = self.docker_manager.config[name]['version']
            containers_info.append(
                {'name': name, 'info': self.docker_manager.get_info_by_config_name(name), 'image_version': version})
        return containers_info

    def get_schains(self):
        containers_info = []
        schain_container_version = self.docker_manager.config.config[SCHAIN_CONTAINER]['version']

        node_id = self.config.safe_get('node_id')
        schains = self.skale.schains_data.get_schains_for_node(node_id)

        for schain in schains:
            container_name = self.docker_manager.construct_schain_container_name(schain['name'])
            healthcheck_value = get_healthcheck_value(schain['name'])
            healthcheck_name = get_healthcheck_name(healthcheck_value)

            containers_info.append({'schain_name': schain['name'],
                                    'name': container_name,
                                    'info': self.docker_manager.get_info(container_name),
                                    'image_version': schain_container_version,
                                    'healthcheck_value': healthcheck_value,
                                    'healthcheck_name': healthcheck_name})
        return containers_info
