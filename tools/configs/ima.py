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
from tools.configs import SCHAIN_CONFIG_DIR_SKALED
from tools.exceptions import MissingEnvVariable


IMA_CONTRACTS = os.getenv('IMA_CONTRACTS')
SCHAIN_IMA_CONTRACTS = 'predeployed'

IMA_NETWORK_BROWSER_FILENAME = 'ima_network_browser_data.json'
IMA_NETWORK_BROWSER_FILEPATH = os.path.join(SCHAIN_CONFIG_DIR_SKALED, IMA_NETWORK_BROWSER_FILENAME)

IMA_STATE_PATH = 'ima_state.json'
IMA_STATE_CONTAINER_PATH = os.path.join(SCHAIN_CONFIG_DIR_SKALED, IMA_STATE_PATH)


DEFAULT_TIME_FRAME = 1800  # 30 min


def ima_contracts() -> str:
    if not IMA_CONTRACTS:
        raise MissingEnvVariable('IMA_CONTRACTS is not set.')
    return IMA_CONTRACTS
