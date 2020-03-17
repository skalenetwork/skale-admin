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
import logging
import secrets

from tools.str_formatters import arguments_list_string
from tools.helper import write_json, read_json
from tools.configs import TOKENS_FILEPATH

logger = logging.getLogger(__name__)


def init_user_token():
    if not os.path.exists(TOKENS_FILEPATH):
        token = generate_user_token()
        logger.info(arguments_list_string({'Token': token}, 'Generated registration token'))
        write_json(TOKENS_FILEPATH, {'token': token})
        return token
    else:
        tokens = read_json(TOKENS_FILEPATH)
        return tokens['token']


def generate_user_token(token_len=40):
    return secrets.token_hex(token_len)
