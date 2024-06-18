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
from tools.configs import (
    CONFIG_FOLDER,
    NODE_DATA_PATH,
    NODE_DATA_PATH_HOST,
    SKALE_LIB_PATH
)

SCHAINS_DIR_NAME = 'schains'
SCHAINS_DIR_PATH = os.path.join(NODE_DATA_PATH, SCHAINS_DIR_NAME)
SCHAINS_DIR_PATH_HOST = os.path.join(NODE_DATA_PATH_HOST, SCHAINS_DIR_NAME)

BASE_SCHAIN_CONFIG_FILENAME = 'schain_base_config.json'
BASE_SCHAIN_CONFIG_FILEPATH = os.path.join(CONFIG_FOLDER, BASE_SCHAIN_CONFIG_FILENAME)

PRECOMPILED_CONTRACTS_FILENAME = 'schain_precompiled_contracts.json'
PRECOMPILED_CONTRACTS_FILEPATH = os.path.join(CONFIG_FOLDER, PRECOMPILED_CONTRACTS_FILENAME)

SCHAIN_SCHECKS_FILENAME = 'checks.json'

SCHAIN_OWNER_ALLOC = 1000000000000000000000000000000
ETHERBASE_ALLOC = 57896044618658097711785492504343953926634992332820282019728792003956564819967
NODE_OWNER_ALLOC = 1000000000000000000000000000000

MAX_SCHAIN_FAILED_RPC_COUNT = int(os.getenv('MAX_SCHAIN_FAILED_RPC_COUNT', 5))

SKALED_STATUS_FILENAME = 'skaled.status'

STATIC_SCHAIN_DIR_NAME = 'schains'
SCHAIN_STATE_PATH = os.path.join(SKALE_LIB_PATH, 'schains')
SCHAIN_STATIC_PATH = os.path.join(SKALE_LIB_PATH, 'filestorage')

DEFAULT_RPC_CHECK_TIMEOUT = 30
RPC_CHECK_TIMEOUT_STEP = 10

MAX_CONSENSUS_STORAGE_INF_VALUE = 1000000000000000000
