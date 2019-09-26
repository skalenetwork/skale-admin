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

import json
from tools.config_storage import ConfigStorage
from tools.encryption import read_encrypted, write_encrypted

class EncryptedStorage(ConfigStorage):
    def __init__(self, path, password, init={}):
        self.password = password
        super().__init__(path, init)

    def _read_config(self):
        plaintext = read_encrypted(self.password, self.path)
        return json.loads(plaintext)

    def _write_config(self, config):
        plaintext = json.dumps(config)
        write_encrypted(self.password, self.path, plaintext)
