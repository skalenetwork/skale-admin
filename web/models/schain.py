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
from datetime import datetime
from peewee import (CharField, DateTimeField,
                    IntegrityError, IntegerField, BooleanField)

from core.schains.dkg.status import DKGStatus
from web.models.base import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_VERSION = '0.0.0'


class SChainRecord(BaseModel):
    name = CharField(unique=True)
    added_at = DateTimeField()
    dkg_status = IntegerField()
    is_deleted = BooleanField(default=False)
    first_run = BooleanField(default=True)
    new_schain = BooleanField(default=True)
    repair_mode = BooleanField(default=False)
    needs_reload = BooleanField(default=False)
    reload_time = DateTimeField()

    monitor_last_seen = DateTimeField()
    monitor_id = IntegerField(default=0)

    config_version = CharField(default=DEFAULT_CONFIG_VERSION)
    restart_count = IntegerField(default=0)
    failed_rpc_count = IntegerField(default=0)

    @classmethod
    def add(cls, name):
        try:
            with cls.database.atomic():
                schain = cls.create(
                    name=name,
                    added_at=datetime.now(),
                    dkg_status=DKGStatus.NOT_STARTED.value,
                    new_schain=True,
                    monitor_last_seen=datetime.now()
                )
            return (schain, None)
        except IntegrityError as err:
            return (None, err)

    @classmethod
    def get_by_name(cls, name):
        return cls.get(cls.name == name)

    @classmethod
    def added(cls, name):
        return cls.select().where(cls.name == name).exists()

    @classmethod
    def get_all_records(cls, include_deleted=False):
        if include_deleted:
            return cls.select()
        else:
            return cls.select().where(cls.is_deleted == False)  # noqa: E712

    @classmethod
    def to_dict(cls, record):
        return {
            'name': record.name,
            'added_at': record.added_at.timestamp(),
            'dkg_status': record.dkg_status,
            'dkg_status_name': DKGStatus(record.dkg_status).name,
            'is_deleted': record.is_deleted,
            'first_run': record.first_run,
            'new_schain': record.new_schain,
            'needs_reload': record.needs_reload,
            'monitor_last_seen': record.monitor_last_seen.timestamp(),
            'monitor_id': record.monitor_id,
            'reload_time': record.reload_time,
            'config_version': record.config_version
        }

    def dkg_started(self):
        self.set_dkg_status(DKGStatus.IN_PROGRESS)

    def dkg_failed(self):
        self.set_dkg_status(DKGStatus.FAILED)

    def dkg_key_generation_error(self):
        self.set_dkg_status(DKGStatus.KEY_GENERATION_ERROR)

    def dkg_done(self):
        self.set_dkg_status(DKGStatus.DONE)

    def set_dkg_status(self, val: DKGStatus) -> None:
        logger.info(f'Changing DKG status for {self.name} to {val.name}')
        self.dkg_status = val.value
        self.save()

    def set_deleted(self):
        self.is_deleted = True
        self.save()

    def set_first_run(self, val):
        logger.info(f'Changing first_run for {self.name} to {val}')
        self.first_run = val
        self.save(only=[SChainRecord.first_run])

    def set_repair_mode(self, value):
        logger.info(f'Changing repair_mode for {self.name} to {value}')
        self.repair_mode = value
        self.save()

    def set_new_schain(self, value):
        logger.info(f'Changing new_schain for {self.name} to {value}')
        self.new_schain = value
        self.save()

    def set_needs_reload(self, value):
        logger.info(f'Changing needs_reload for {self.name} to {value}')
        self.needs_reload = value
        self.save()

    def set_reload_time(self, value):
        logger.info(f'Changing reload_time for {self.name} to {value}')
        self.reload_time = value
        self.save()

    def set_monitor_last_seen(self, value):
        logger.info(f'Changing monitor_last_seen for {self.name} to {value}')
        self.monitor_last_seen = value
        self.save()

    def set_monitor_id(self, value):
        logger.info(f'Changing monitor_id for {self.name} to {value}')
        self.monitor_id = value
        self.save()

    def set_config_version(self, value):
        logger.info(f'Changing config_version for {self.name} to {value}')
        self.config_version = value
        self.save()

    def set_restart_count(self, value: int) -> None:
        logger.info(f'Changing restart count for {self.name} to {value}')
        self.restart_count = value
        self.save()

    def set_failed_rpc_count(self, value: int) -> None:
        logger.info(f'Changing failed rpc count for {self.name} to {value}')
        self.failed_rpc_count = value
        self.save()

    def reset_failed_conunters(self) -> None:
        logger.info(f'Resetting failed counters for {self.name}')
        self.set_restart_count(0)
        self.set_failed_rpc_count(0)

    def is_dkg_done(self) -> bool:
        return self.dkg_status == DKGStatus.DONE.value

    def is_dkg_unsuccessful(self) -> bool:
        return self.dkg_status in [
            DKGStatus.KEY_GENERATION_ERROR.value,
            DKGStatus.FAILED.value
        ]


def create_tables():
    logger.info('Creating schainrecord table...')
    if not SChainRecord.table_exists():
        SChainRecord.create_table()


def set_schains_first_run():
    logger.info('Setting first_run=True for all sChain records')
    query = SChainRecord.update(first_run=True).where(
        SChainRecord.first_run == False)  # noqa
    query.execute()


def set_schains_need_reload():
    logger.info('Setting needs_reload=True for all sChain records')
    query = SChainRecord.update(needs_reload=True).where(
        SChainRecord.needs_reload == False)  # noqa
    query.execute()


def set_schains_monitor_id():
    logger.info('Setting monitor_id=0 for all sChain records')
    query = SChainRecord.update(monitor_id=0).where(
        SChainRecord.monitor_id != 0)  # noqa
    query.execute()


def upsert_schain_record(name):
    if not SChainRecord.added(name):
        logger.debug(f'Could not find sChain record: {name}, going to add')
        schain_record, _ = SChainRecord.add(name)
    else:
        logger.debug(f'Getting sChain record by name: {name}')
        schain_record = SChainRecord.get_by_name(name)

    if not schain_record:
        logger.error(f'schain_record is None for {name}')

    return schain_record


def mark_schain_deleted(name):
    if SChainRecord.added(name):
        schain_record = SChainRecord.get_by_name(name)
        schain_record.set_deleted()


def set_first_run(name, value):
    if SChainRecord.added(name):
        schain_record = SChainRecord.get_by_name(name)
        schain_record.set_first_run(value)


def get_schains_names(include_deleted=False):
    return [r.name for r in SChainRecord.get_all_records(include_deleted)]


def get_schains_statuses(include_deleted=False):
    return [SChainRecord.to_dict(r)
            for r in SChainRecord.get_all_records(include_deleted)]


def toggle_schain_repair_mode(name):
    logger.info(f'Toggling repair mode for schain {name}')
    query = SChainRecord.update(repair_mode=True).where(
        SChainRecord.name == name)
    count = query.execute()
    return count > 0
