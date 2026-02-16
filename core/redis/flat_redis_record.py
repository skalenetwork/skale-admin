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

import abc
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tools.resources import rs

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    name: str
    type: type
    default: str | int | bool | datetime | None


class FlatRedisRecord:
    def __init__(self, name: str):
        self.name = name
        if not self._exists():
            self._set_defaults()
            self._save()

    def to_dict(self) -> dict:
        return self.mget(*self._record_fields().keys())

    def mget(self, *args) -> dict[str, Any]:
        key_names = [self._get_field_key(field_name) for field_name in args]
        raw_res = rs.mget(*key_names)
        return {
            key_name: self._deserialize_field(value, self._record_fields()[key_name].type)
            for value, key_name in zip(raw_res, args)
        }

    def mset(self, **kwargs) -> None:
        key_names = [self._get_field_key(field_name) for field_name in kwargs.keys()]
        values = [
            self._serialize_field(value, self._record_fields()[field_name].type)
            for value, field_name in zip(kwargs.values(), kwargs.keys())
        ]
        rs.mset(dict(zip(key_names, values)))

    def delete(self) -> None:
        rs.delete(*self._key_names())

    def _get_field_key(self, field_name: str) -> str:
        return f'{self.name}_{field_name}'

    def _serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    def _deserialize_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)

    def _get_field(self, field_name: str):
        key = self._get_field_key(field_name)
        value = rs.get(key)
        return self._deserialize_field(value, self._record_fields()[field_name].type)

    def _set_field(self, field_name: str, value) -> None:
        key = self._get_field_key(field_name)
        serialized_value = self._serialize_field(value, self._record_fields()[field_name].type)
        logger.info('Setting field %s to value %s', field_name, serialized_value)
        rs.set(key, serialized_value)

    def _deserialize_field(self, value, field_type: type):
        if value is None:
            return None
        val = value.decode('utf-8')
        if field_type is datetime:
            return self._deserialize_datetime(val)
        elif field_type is bool:
            return bool(int(val))
        elif field_type is int:
            return int(val)
        else:
            return val

    def _serialize_field(self, value, field_type: type):
        if field_type is datetime:
            return self._serialize_datetime(value)
        elif field_type is bool:
            return int(value)
        elif field_type is int:
            return value
        else:
            return str(value)

    def _key_names(self) -> list[str]:
        return [self._get_field_key(field_name) for field_name in self._record_fields().keys()]

    def _set_defaults(self) -> None:
        record_fields = self._record_fields()
        defaults_to_set = {
            field_name: field_info.default
            for field_name, field_info in record_fields.items()
            if field_info.default is not None
        }
        if defaults_to_set:
            self.mset(**defaults_to_set)

    def _exists(self) -> bool:
        return rs.exists(self._get_field_key('name')) > 0

    def _save(self) -> None:
        self._set_field('name', self.name)

    @abc.abstractmethod
    def _record_fields(self) -> dict[str, FieldInfo]:
        """Return a list of FieldInfo objects representing the fields of the record."""

    @classmethod
    def _redis_key_to_field_name(cls, key: bytes) -> str:
        return key[:-5].decode('utf-8')

    @classmethod
    def find_all(cls) -> list['FlatRedisRecord']:
        name_keys = rs.keys('*_name')
        records = []
        for key in name_keys:
            chain_name = cls._redis_key_to_field_name(key)
            records.append(cls(chain_name))
        return records

    def __eq__(self, other) -> bool:
        if not isinstance(other, FlatRedisRecord):
            return False
        return self.name == other.name
