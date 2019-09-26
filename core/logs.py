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
import fnmatch
import urllib
import datetime
import shlex

from tools.config import LOG_FOLDER, SCHAINS_DIR_PATH, SCHAIN_LOG_PATTERN
from tools.helper import files, run_cmd
from tools.docker_utils import DockerUtils

#from core.schains.helper import get_schain_ports

BASE_DOWNLOAD_URL = '/download-log-file'


class Logs():
    def __init__(self):
        self.docker_utils = DockerUtils()

    def get_all_info(self):
        logs_info = {
            'base': [],
            'schains': {}
        }

        for file in files(LOG_FOLDER):
            full_path = os.path.join(LOG_FOLDER, file)
            info = os.stat(full_path)

            filename, file_ext = os.path.splitext(file)
            params = urllib.parse.urlencode({'type': 'base', 'filename': file})

            logs_info['base'].append({
                'created_at': info.st_ctime,
                'size': info.st_size,
                'download_url': f'{BASE_DOWNLOAD_URL}?{params}',
                'type': 'base',
                'name': file
            })

        schain_dirs = os.listdir(SCHAINS_DIR_PATH)
        for schain_name in schain_dirs:
            # schain_data_dir = get_schain_data_dir(schain_name)
            schain_data_dir = f'/var/lib/docker/volumes/{schain_name}/_data'  # todo: tmp fix - use docker log dirver instead!

            if not os.path.isdir(schain_data_dir):
                continue

            log_files = fnmatch.filter(os.listdir(schain_data_dir), SCHAIN_LOG_PATTERN)

            for idx, lf in enumerate(log_files):
                full_path = os.path.join(schain_data_dir, lf)

                if not os.path.isfile(full_path):
                    continue

                # rpc_ports = get_schain_ports(schain_name)

                info = os.stat(full_path)
                params = urllib.parse.urlencode(
                    {'type': 'schain', 'schain_name': schain_name, 'filename': lf})

                if not logs_info['schains'].get(schain_name, None):
                    logs_info['schains'][schain_name] = {'info': {'ports': []}, 'logs': []}

                logs_info['schains'][schain_name]['logs'].append({
                    # 'path': full_path,
                    'created_at': info.st_ctime,
                    'size': info.st_size,
                    'download_url': f'{BASE_DOWNLOAD_URL}?{params}',
                    'type': 'schain',
                    'name': lf,
                    'schain': schain_name
                })

        return logs_info

    def get_filepath(self, type, filename=None, schain_name=None):  # todo!
        time = datetime.datetime.now()
        if type == 'schain':
            # schain_datadir_path = get_schain_data_dir(schain_name)
            schain_datadir_path = f'/var/lib/docker/volumes/{schain_name}/_data'  # todo: tmp fix - use docker log dirver instead!
            return os.path.join(schain_datadir_path,
                                filename), f'{filename}_{schain_name}_{time}.log'
        else:
            return os.path.join(LOG_FOLDER, filename), f'{filename}_{time}.log'

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
