#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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
from typing import cast

from core.redis.flat_redis_record import FieldInfo, FlatRedisRecord

logger = logging.getLogger(__name__)


RECORD_FIELDS: dict[str, FieldInfo] = {
    'name': FieldInfo('name', str, None),
    'local_endpoint': FieldInfo('local_endpoint', str, None),
}


class NodeConfigFair(FlatRedisRecord):
    def __init__(self):
        self.name = 'node_config_fair'
        if not self._exists():
            self._set_defaults()
            self._save()

    def _record_fields(self) -> dict[str, FieldInfo]:
        return RECORD_FIELDS

    @property
    def local_endpoint(self) -> str:
        return cast(str, self._get_field('local_endpoint'))

    def set_local_endpoint(self, local_endpoint: str) -> None:
        self._set_field('local_endpoint', local_endpoint)
