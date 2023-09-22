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
from tools.configs import CONFIG_FOLDER
from tools.helper import read_json

DATA_DIR_CONTAINER_PATH = '/data_dir'
SHARED_SPACE_CONTAINER_PATH = '/shared-space'
SHARED_SPACE_VOLUME_NAME = 'shared-space'

SCHAIN_CONTAINER = 'schain'
IMA_CONTAINER = 'ima'

CONTAINER_NAME_PREFIX = 'skale'
CONTAINERS_FILENAME = 'containers.json'

CONTAINERS_FILEPATH = os.path.join(CONFIG_FOLDER, CONTAINERS_FILENAME)

CONTAINERS_INFO = read_json(CONTAINERS_FILEPATH)

IMA_MIGRATION_FILENAME = 'ima_migration_schedule.yaml'
IMA_MIGRATION_PATH = os.path.join(CONFIG_FOLDER, IMA_MIGRATION_FILENAME)

CONTAINER_NOT_FOUND = 'not_found'
EXITED_STATUS = 'exited'
CREATED_STATUS = 'created'
RUNNING_STATUS = 'running'

LOCAL_IP = '127.0.0.1'

DOCKER_DEFAULT_HEAD_LINES = 400
DOCKER_DEFAULT_TAIL_LINES = 10000

DOCKER_DEFAULT_STOP_TIMEOUT = 20

SCHAIN_STOP_TIMEOUT = int(os.getenv('SCHAIN_STOP_TIMEOUT', 300))

DEFAULT_DOCKER_HOST = 'unix:///var/run/skale/docker.sock'

MAX_SCHAIN_RESTART_COUNT = int(os.getenv('MAX_SCHAIN_RESTART_COUNT', 5))

CONTAINER_LOGS_SEPARATOR = b'=' * 80 + b'\n'
