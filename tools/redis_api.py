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

import json
from functools import partial
from typing import Dict, List, Optional

import redis

grs = redis.Redis(connection_pool=redis.BlockingConnectionPool())


def record_from_bytes(record_bytes: bytes) -> Dict:
    return json.loads(record_bytes.decode('utf-8'))


def get_record(key: bytes, rs: redis.Redis = grs) -> Optional[Dict]:
    raw_record = rs.get(key)
    if raw_record:
        return record_from_bytes(raw_record)
    return None


def get_zset_size(pname: str, rs: redis.Redis = grs) -> int:
    return rs.zcard(pname)


def get_zset_as_list(pname: str, rs: redis.Redis = grs) -> List[bytes]:
    return rs.zrange(pname, 0, -1)


def get_zset_keys(pname: str, rs: redis.Redis = grs):
    return [
        raw_key.decode('utf-8')
        for raw_key in get_zset_as_list(pname, rs)
    ]


def are_meta_and_method_same(
    key: bytes,
    meta: Optional[Dict] = None,
    method: Optional[str] = None
) -> bool:
    record = get_record(key)
    return (meta is None or record.get('meta') == meta) \
        and (method is None or record.get('method') == method)


def get_records_by_meta_and_method(
    pname: str,
    rs: redis.Redis = grs,
    meta: Optional[Dict] = None,
    method: Optional[str] = None
) -> List[Dict]:
    predicate = partial(are_meta_and_method_same, meta=meta, method=method)
    return list(filter(predicate, get_zset_keys(pname, rs)))
