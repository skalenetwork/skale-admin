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
from datetime import datetime

from core.redis.flat_redis_record import FieldInfo, FlatRedisRecord
from core.schains.dkg.structures import DKGStatus

logger = logging.getLogger(__name__)


RECORD_FIELDS: dict[str, FieldInfo] = {
    'name': FieldInfo('name', str, None),
    'config_version': FieldInfo('config_version', str, '0.0.0'),
    'sync_config_run': FieldInfo('sync_config_run', bool, False),
    'first_run': FieldInfo('first_run', bool, False),
    'backup_run': FieldInfo('backup_run', bool, False),
    'restart_count': FieldInfo('restart_count', int, 0),
    'failed_rpc_count': FieldInfo('failed_rpc_count', int, 0),
    'monitor_last_seen': FieldInfo('monitor_last_seen', datetime, datetime.fromtimestamp(0)),
    'ssl_change_date': FieldInfo('ssl_change_date', datetime, datetime.fromtimestamp(0)),
    'repair_date': FieldInfo('repair_date', datetime, datetime.fromtimestamp(0)),
    'dkg_status': FieldInfo('dkg_status', int, DKGStatus.NOT_STARTED.value),
    'repair_ts': FieldInfo('repair_ts', int, None),
    'snapshot_from': FieldInfo('snapshot_from', str, None),
}


class ChainRecord(FlatRedisRecord):
    def _record_fields(self) -> dict[str, FieldInfo]:
        return RECORD_FIELDS

    @property
    def config_version(self) -> str:
        return cast(str, self._get_field('config_version'))

    @property
    def sync_config_run(self) -> bool:
        return cast(bool, self._get_field('sync_config_run'))

    @property
    def first_run(self) -> bool:
        return cast(bool, self._get_field('first_run'))

    @property
    def backup_run(self) -> bool:
        return cast(bool, self._get_field('backup_run'))

    @property
    def restart_count(self) -> int:
        return cast(int, self._get_field('restart_count'))

    @property
    def failed_rpc_count(self) -> int:
        return cast(int, self._get_field('failed_rpc_count'))

    @property
    def monitor_last_seen(self) -> datetime:
        return cast(datetime, self._get_field('monitor_last_seen'))

    @property
    def ssl_change_date(self) -> datetime:
        return cast(datetime, self._get_field('ssl_change_date'))

    @property
    def repair_date(self) -> datetime:
        return cast(datetime, self._get_field('repair_date'))

    @property
    def dkg_status(self) -> DKGStatus:
        return cast(DKGStatus, self._get_field('dkg_status'))

    @property
    def snapshot_from(self) -> str | None:
        return cast(str | None, self._get_field('snapshot_from'))

    @property
    def repair_ts(self) -> int | None:
        return cast(int | None, self._get_field('repair_ts'))

    def set_config_version(self, version: str) -> None:
        self._set_field('config_version', version)

    def set_sync_config_run(self, value: bool) -> None:
        self._set_field('sync_config_run', value)

    def set_first_run(self, value: bool) -> None:
        self._set_field('first_run', value)

    def set_restart_count(self, count: int) -> None:
        self._set_field('restart_count', count)

    def set_failed_rpc_count(self, count: int) -> None:
        self._set_field('failed_rpc_count', count)

    def set_monitor_last_seen(self, last_seen: datetime) -> None:
        self._set_field('monitor_last_seen', last_seen)

    def set_dkg_status(self, status: DKGStatus) -> None:
        self._set_field('dkg_status', status)

    def set_ssl_change_date(self, date: datetime) -> None:
        self._set_field('ssl_change_date', date)

    def set_repair_date(self, date: datetime) -> None:
        self._set_field('repair_date', date)

    def set_backup_run(self, value: bool) -> None:
        self._set_field('backup_run', value)

    def set_snapshot_from(self, value: str | None) -> None:
        self._set_field('snapshot_from', value)

    def set_repair_ts(self, value: int | None) -> None:
        self._set_field('repair_ts', value)

    def reset_failed_counters(self) -> None:
        logger.info(f'Resetting failed counters for {self.name}')
        self.set_restart_count(0)
        self.set_failed_rpc_count(0)
