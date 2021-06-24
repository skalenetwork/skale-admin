#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
import json
import shutil
import logging
from ima_predeployed.generator import generate_abi, generate_contracts

from core.schains.helper import get_schain_dir_path
from tools.helper import read_json
from tools.configs.ima import (
    SCHAIN_IMA_ABI_FILEPATH, SCHAIN_IMA_ABI_FILENAME, MAINNET_IMA_ABI_FILEPATH,
    IMA_STATE_PATH
)


logger = logging.getLogger(__name__)


def update_predeployed_ima():
    """
    Generates a new ABI for predeployed IMA using ima_predeployed library, saves the results
    in contracts_info folder.
    """
    logger.info(f'Going to generate a new ABI file for sChain IMA ({SCHAIN_IMA_ABI_FILEPATH})')
    with open(SCHAIN_IMA_ABI_FILEPATH, 'w') as outfile:
        json.dump(generate_abi(), outfile, indent=4)
    logger.info(f'New ABI file for sChain IMA saved: {SCHAIN_IMA_ABI_FILEPATH}')


def copy_schain_ima_abi(name):
    abi_file_dest = get_schain_ima_abi_filepath(name)
    logger.info(f'Copying {SCHAIN_IMA_ABI_FILEPATH} -> {abi_file_dest}')
    shutil.copyfile(SCHAIN_IMA_ABI_FILEPATH, abi_file_dest)


def get_schain_ima_abi_filepath(schain_name):
    schain_dir_path = get_schain_dir_path(schain_name)
    return os.path.join(schain_dir_path, SCHAIN_IMA_ABI_FILENAME)


def get_schain_ima_state_filepath(schain_name):
    return os.path.join(get_schain_dir_path(schain_name), IMA_STATE_PATH)


def generate_ima_accounts(schain_owner, schain_name):
    mainnet_ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)
    return generate_contracts(
        owner_address=schain_owner,
        schain_name=schain_name,
        contracts_on_mainnet=mainnet_ima_abi
    )


def get_message_proxy_addresses():
    mainnet_ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)
    schain_ima_abi = read_json(SCHAIN_IMA_ABI_FILEPATH)
    ima_mp_schain = schain_ima_abi['message_proxy_chain_address']
    ima_mp_mainnet = mainnet_ima_abi['message_proxy_mainnet_address']
    return {
        'ima_message_proxy_schain': ima_mp_schain,
        'ima_message_proxy_mainnet': ima_mp_mainnet
    }
