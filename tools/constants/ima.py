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

from pathlib import Path

from tools.constants import CONTRACTS_INFO_FOLDER, SCHAIN_CONFIG_DIR_SKALED

# legacy variables, used only to run ima-agent
_IMA_MAINNET_ABI_FILEPATH: Path = CONTRACTS_INFO_FOLDER / '.ima_mainnet_abi.json'
_IMA_SCHAIN_ABI_FILEPATH: Path = CONTRACTS_INFO_FOLDER / '.ima_schain_abi.json'
_MANAGER_ABI_FILEPATH: Path = CONTRACTS_INFO_FOLDER / '.manager_abi.json'

IMA_NETWORK_BROWSER_FILENAME: str = 'ima_network_browser_data.json'
IMA_NETWORK_BROWSER_FILEPATH: Path = SCHAIN_CONFIG_DIR_SKALED / IMA_NETWORK_BROWSER_FILENAME

IMA_STATE_PATH: str = 'ima_state.json'
IMA_STATE_CONTAINER_PATH: Path = SCHAIN_CONFIG_DIR_SKALED / IMA_STATE_PATH

DEFAULT_TIME_FRAME = 1800  # 30 min
