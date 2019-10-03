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

import logging
import secrets

from tools.config_storage import ConfigStorage
from tools.configs import TOKENS_FILEPATH

logger = logging.getLogger(__name__)


class TokenUtils():
    def __init__(self, filepath=TOKENS_FILEPATH):
        self.filepath = filepath
        self.token_storage = ConfigStorage(filepath)

    def add_token(self):
        token = self.generate_new_token()
        self.save_token(token)

    def generate_new_token(self, len=40):
        return secrets.token_hex(len)

    def save_token(self, token):
        self.token_storage.update({'token': token})

    def get_token(self):
        return self.token_storage.safe_get('token')