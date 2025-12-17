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

import json
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar, cast, overload

from redis import Redis
from redis.exceptions import RedisError
from skale import SkaleManager
from skale.types.node import NodeId

T = TypeVar('T')


@dataclass(frozen=True, slots=True)
class CacheSpec(Generic[T]):
    name: str
    ttl: int
    fetch: Callable[['RedisCache'], T]
    ser: Callable[[T], bytes]
    de: Callable[[bytes], T]
    refresh_if: Callable[['RedisCache', T], bool] | None = None


class cached(Generic[T]):
    def __init__(self, spec: CacheSpec[T]) -> None:
        self.spec = spec

    @overload
    def __get__(self, obj: None, owner: type[Any]) -> 'cached[T]': ...
    @overload
    def __get__(self, obj: 'RedisCache', owner: type[Any]) -> T: ...

    def __get__(self, obj: Any, owner: type[Any]) -> Any:
        return self if obj is None else obj.get(self.spec)


def json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode()


def json_obj(raw: bytes) -> Any:
    return json.loads(raw.decode())


def hex_to_bytes(s: str) -> bytes:
    if s.startswith(('0x', '0X')):
        s = s[2:]
    return bytes.fromhex(s)


class RedisCache:
    key_prefix = 'redis-cache:v1'

    def __init__(self, redis: Redis, skale: SkaleManager, node_id: NodeId) -> None:
        self.redis, self.skale, self.node_id = redis, skale, node_id

    def get(self, spec: CacheSpec[T]) -> T:
        key = f'{self.key_prefix}:{spec.name}'

        try:
            raw = self.redis.get(key)
        except (OSError, RedisError):
            raw = None

        if isinstance(raw, (bytes, str, memoryview)):
            try:
                val = spec.de(cast(bytes, raw))
                if spec.refresh_if is None or not spec.refresh_if(self, val):
                    return val
            except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, KeyError):
                pass

        val = spec.fetch(self)
        try:
            self.redis.setex(key, spec.ttl, spec.ser(val))
        except (OSError, RedisError):
            pass
        return val
