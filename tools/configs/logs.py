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
from tools.configs import NODE_DATA_PATH

LOG_FOLDER_NAME = 'log'
LOG_FOLDER = os.path.join(NODE_DATA_PATH, LOG_FOLDER_NAME)

ADMIN_LOG_FILENAME = 'admin.log'
ADMIN_LOG_PATH = os.path.join(LOG_FOLDER, ADMIN_LOG_FILENAME)

API_LOG_FILENAME = 'api.log'
API_LOG_PATH = os.path.join(LOG_FOLDER, API_LOG_FILENAME)

DEBUG_LOG_FILENAME = 'debug.log'
DEBUG_LOG_PATH = os.path.join(LOG_FOLDER, DEBUG_LOG_FILENAME)

SYNC_LOG_FILENAME = 'sync_node.log'
SYNC_LOG_PATH = os.path.join(LOG_FOLDER, SYNC_LOG_FILENAME)


REMOVED_CONTAINERS_FOLDER_NAME = '.removed_containers'
REMOVED_CONTAINERS_FOLDER_PATH = os.path.join(
    LOG_FOLDER,
    REMOVED_CONTAINERS_FOLDER_NAME
)

LOG_FILE_SIZE_MB = 100
LOG_FILE_SIZE_BYTES = LOG_FILE_SIZE_MB * 1000000

LOG_BACKUP_COUNT = 20

ADMIN_LOG_FORMAT = '[%(asctime)s %(levelname)s][%(process)d][%(processName)s][%(threadName)s] - %(name)s:%(lineno)d - %(message)s'  # noqa
API_LOG_FORMAT = '[%(asctime)s] %(process)d %(levelname)s %(url)s %(module)s: %(message)s'  # noqa
