#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022 SKALE Labs
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

from tools.json_object import JsonObject
from tools.configs import NODE_OPTIONS_FILEPATH


logger = logging.getLogger(__name__)


class NodeOptions(JsonObject):
    def __init__(self):
        super().__init__(filepath=NODE_OPTIONS_FILEPATH)

    @property
    def archive(self) -> bool:
        return self._get('archive')

    @property
    def catchup(self) -> bool:
        return self._get('catchup')

    @property
    def historic_state(self) -> bool:
        return self._get('historic_state')

    @property
    def schain_base_port(self) -> int:
        return self._get('schain_base_port') or -1
