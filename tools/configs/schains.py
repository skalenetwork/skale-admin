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
from tools.configs import NODE_DATA_PATH, CONFIG_FOLDER, NODE_DATA_PATH_HOST

SCHAINS_DIR_NAME = 'schains'
SCHAINS_DIR_PATH = os.path.join(NODE_DATA_PATH, SCHAINS_DIR_NAME)
SCHAINS_DIR_PATH_HOST = os.path.join(NODE_DATA_PATH_HOST, SCHAINS_DIR_NAME)

DATA_DIR_NAME = 'data_dir'

BASE_SCHAIN_CONFIG_FILENAME = 'schain_base_config.json'
BASE_SCHAIN_CONFIG_FILEPATH = os.path.join(CONFIG_FOLDER, BASE_SCHAIN_CONFIG_FILENAME)

FILESTORAGE_ARTIFACTS_FILENAME = 'filestorage_artifacts.json'
FILESTORAGE_ARTIFACTS_FILEPATH = os.path.join(NODE_DATA_PATH, FILESTORAGE_ARTIFACTS_FILENAME)

STATIC_SCHAIN_PARAMS_FILENAME = 'static_schain_params.json'
STATIC_SCHAIN_PARAMS_FILEPATH = os.path.join(CONFIG_FOLDER, STATIC_SCHAIN_PARAMS_FILENAME)

SCHAIN_OWNER_ALLOC = 1000000000000000000000  # todo: tmp!
NODE_OWNER_ALLOC = 1000000000000000000000  # todo: tmp!
