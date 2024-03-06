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

from tools.configs import NODE_CONFIG_FILEPATH
from tools.json_object import JsonObject

logger = logging.getLogger(__name__)


class NodeConfig(JsonObject):
    def __init__(self, filepath: str = NODE_CONFIG_FILEPATH):
        super().__init__(filepath=filepath)

    @property
    def id(self) -> int:
        return self._get('node_id')

    @id.setter
    def id(self, node_id: int) -> None:
        return self._set('node_id', node_id)

    @property
    def ip(self) -> str:
        return self._get('node_ip')

    @ip.setter
    def ip(self, ip: str) -> None:
        return self._set('node_ip', ip)

    @property
    def name(self) -> str:
        return self._get('name')

    @name.setter
    def name(self, node_name: str) -> None:
        return self._set('name', node_name)

    @property
    def sgx_key_name(self) -> int:
        return self._get('sgx_key_name')

    @sgx_key_name.setter
    def sgx_key_name(self, sgx_key_name: int) -> None:
        return self._set('sgx_key_name', sgx_key_name)
