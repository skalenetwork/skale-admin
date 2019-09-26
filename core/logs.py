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

import os
import datetime
import shlex

from tools.helper import run_cmd
from tools.docker_utils import DockerUtils


class Logs():
    def __init__(self):
        self.docker_utils = DockerUtils()

    def get_container_logs(self, container_name, tail="all", stream=False):
        return self.docker_utils.cli.logs(container_name, timestamps=True, tail=tail, stream=stream)

    def get_containers_logs(self, container_name=None):
        folder_path, dump_name = self.create_dump_dir()
        filter_name = container_name if container_name else 'skale'
        containers = self.docker_utils.cli.containers(filters={'name': filter_name}, all=True)

        for container in containers:
            name = container['Names'][0].replace('/', '', 1)
            logs = self.get_container_logs(name)
            log_filename = f'{name}.log'
            log_filepath = os.path.join(folder_path, log_filename)
            log_file = open(log_filepath, "wb")
            log_file.write(logs)

        if len(containers) == 0:
            return None, None

        archive_name = f'{dump_name}.tar.gz'
        archive_path = os.path.join(folder_path, archive_name)
        self.create_archive(archive_path, folder_path)
        return archive_path, archive_name

    def create_dump_dir(self):
        time = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H:%M:%S")
        folder_name = f'skale-logs-dump-{time}'
        folder_path = os.path.join('/tmp', folder_name)
        os.mkdir(folder_path)
        return folder_path, folder_name

    def create_archive(self, zipname, path):
        files = os.listdir(path)
        files_str = ' '.join(files)
        cmd = shlex.split(f'tar -czvf {zipname} -C {path} {files_str}')
        run_cmd(cmd)
