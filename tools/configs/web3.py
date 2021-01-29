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
from tools.configs import CONTRACTS_INFO_FOLDER, MANAGER_CONTRACTS_INFO_NAME
from tools.configs import NODE_DATA_PATH

TM_URL = os.environ['TM_URL']
ENDPOINT = os.environ['ENDPOINT']
ABI_FILEPATH = os.getenv('ABI_FILEPATH') or \
            os.path.join(CONTRACTS_INFO_FOLDER, MANAGER_CONTRACTS_INFO_NAME)
STATE_FILENAME = os.getenv('STATE_FILENAME')
STATE_BASE_PATH = os.path.join(NODE_DATA_PATH, 'eth-state')
STATE_FILEPATH = None if not STATE_FILENAME \
                    else os.path.join(STATE_BASE_PATH, STATE_FILENAME)

NODE_REGISTER_CONFIRMATION_BLOCKS = 5
