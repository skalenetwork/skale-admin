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


from tools.helper import read_json
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH, IMA_DATA_FILEPATH


def get_message_proxy_addresses():
    ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)
    schain_ima_abi = read_json(IMA_DATA_FILEPATH)
    ima_mp_schain = schain_ima_abi['message_proxy_chain_address']
    ima_mp_mainnet = ima_abi['message_proxy_mainnet_address']
    return {
        'ima_message_proxy_schain': ima_mp_schain,
        'ima_message_proxy_mainnet': ima_mp_mainnet
    }
