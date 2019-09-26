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

SKALE_VOLUME_PATH = '/skale_vol'
NODE_DATA_PATH = '/skale_node_data'

CONFIG_FOLDER_NAME = 'config'
LOG_FOLDER_NAME = 'log'
CONTRACTS_INFO_FOLDER_NAME = 'contracts_info'

MANAGER_CONTRACTS_INFO_NAME = 'manager.json'
IMA_CONTRACTS_INFO_NAME = 'ima.json'
DKG_CONTRACTS_INFO_NAME = 'dkg.json'

CONTRACTS_INFO_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONTRACTS_INFO_FOLDER_NAME)

# project dirs

HERE = os.path.dirname(os.path.realpath(__file__))
PROJECT_DIR = os.path.join(HERE, os.pardir)
PROJECT_CONFIG_FOLDER = os.path.join(PROJECT_DIR, 'config')
PROJECT_TOOLS_FOLDER = os.path.join(PROJECT_DIR, 'tools')
PROJECT_LOG_FOLDER = os.path.join(PROJECT_DIR, LOG_FOLDER_NAME)

CONTAINERS_FILENAME = 'containers.json'

BUILD_LOG_FILENAME = 'build.log'
BUILD_LOG_PATH = os.path.join(PROJECT_LOG_FOLDER, BUILD_LOG_FILENAME)

PROJECT_ABI_FILEPATH = os.path.join(PROJECT_CONFIG_FOLDER, MANAGER_CONTRACTS_INFO_NAME)


## node data

# logs

LOG_FOLDER = os.path.join(NODE_DATA_PATH, LOG_FOLDER_NAME)

ADMIN_LOG_FILENAME = 'admin.log'
ADMIN_LOG_PATH = os.path.join(LOG_FOLDER, ADMIN_LOG_FILENAME)

DEBUG_LOG_FILENAME = 'debug.log'
DEBUG_LOG_PATH = os.path.join(LOG_FOLDER, DEBUG_LOG_FILENAME)

LOG_FILE_SIZE_MB = 100
LOG_FILE_SIZE_BYTES = LOG_FILE_SIZE_MB * 1000000

LOG_BACKUP_COUNT = 3

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# schains

SCHAINS_DIR_NAME = 'schains'
SCHAINS_DIR_PATH = os.path.join(NODE_DATA_PATH, SCHAINS_DIR_NAME)
DATA_DIR_NAME = 'data_dir'
DATA_DIR_CONTAINER_PATH = '/data_dir'

HEALTHCHECK_FILENAME = 'HEALTH_CHECK'
HEALTHCHECK_STATUSES = {'-1': 'not inited', '-2': 'wrong value', '0': 'fail', '1': 'passing', '2': 'passed'}

# sqlite db

DB_FILENAME = 'skale.db'
DB_FILE = os.path.join(NODE_DATA_PATH, DB_FILENAME)

# other

LOCAL_WALLET_FILENAME = 'local_wallet.json'
LOCAL_WALLET_FILEPATH = os.path.join(NODE_DATA_PATH, LOCAL_WALLET_FILENAME)

TOKENS_FILENAME = 'tokens.json'
TOKENS_FILEPATH = os.path.join(NODE_DATA_PATH, TOKENS_FILENAME)

FLASK_SECRET_KEY_FILENAME = 'flask_db_key.txt'
FLASK_SECRET_KEY_FILE = os.path.join(NODE_DATA_PATH, FLASK_SECRET_KEY_FILENAME)

NODE_CONFIG_FILENAME = 'node_config.json'
NODE_CONFIG_FILEPATH = os.path.join(NODE_DATA_PATH, NODE_CONFIG_FILENAME)

## skale vol

CONFIG_FOLDER = os.path.join(SKALE_VOLUME_PATH, CONFIG_FOLDER_NAME)


CUSTOM_CONTRACTS_PATH = os.path.join(CONTRACTS_INFO_FOLDER, MANAGER_CONTRACTS_INFO_NAME)

BASE_SCHAIN_CONFIG_FILENAME = 'schain_base_config.json'

CONTAINERS_FILEPATH = os.path.join(CONFIG_FOLDER, CONTAINERS_FILENAME)

PROXY_ABI_FILENAME = 'proxy.json'
BASE_SCHAIN_CONFIG_FILEPATH = os.path.join(CONFIG_FOLDER, BASE_SCHAIN_CONFIG_FILENAME)
MAINNET_PROXY_PATH = os.path.join(CONTRACTS_INFO_FOLDER, IMA_CONTRACTS_INFO_NAME)

# server

EVENTS_POLL_INTERVAL = 5

# docker

SKALE_PREFIX = 'skalelabshub'
CONTAINER_NAME_PREFIX = 'skale_'
DOCKER_USERNAME = os.environ.get('DOCKER_USERNAME')
DOCKER_PASSWORD = os.environ.get('DOCKER_PASSWORD')

CONTAINER_FORCE_STOP_TIMEOUT = 20

TEST_PWD = 11111111

PORTS_PER_SCHAIN = 11

# sChain config

SCHAIN_OWNER_ALLOC = 1000000000000000000000
#NODE_OWNER_ALLOC = 1000000000000000000
NODE_OWNER_ALLOC = 1000000000000000000000 # todo: tmp!

# mta

MTA_CONFIG_NAME = 'mta'

# SSL

SSL_CERTIFICATES_FILENAME = 'ssl'
SSL_CERTIFICATES_FILEPATH = os.path.join(NODE_DATA_PATH, SSL_CERTIFICATES_FILENAME)
ALLOWED_SSL_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

#

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
