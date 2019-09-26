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

from tools.config import LOCAL_WALLET_FILEPATH
from encrypted_storage import EncryptedStorage


class LocalWallet():
    def __init__(self, password):
        self.filepath = LOCAL_WALLET_FILEPATH
        self.encrypted_storage = EncryptedStorage(LOCAL_WALLET_FILEPATH, password)

    def get(self):
        return self.encrypted_storage.get()

    def update(self, text):
        self.encrypted_storage.update(text)
