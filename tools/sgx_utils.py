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
from sgx import SgxClient

nek_config_item = 'NODE_ELASTIC_KEY_NAME'


def generate_sgx_key(config):
    if not os.environ.get('SGX_SERVER_URL', None) or config[nek_config_item]:
        return
    sgx = SgxClient(os.environ['SGX_SERVER_URL'])
    key_name = sgx.generate_key().keyName
    save_sgx_key(key_name, config)


def save_sgx_key(key_name, config):
    config.update({nek_config_item: key_name})

