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
import datetime
from peewee import CharField, DateTimeField, IntegrityError, IntegerField, BooleanField

from core.schains.dkg_status import DKGStatus
from web.models.base import BaseModel

logger = logging.getLogger(__name__)


class SChainRecord(BaseModel):
    name = CharField(unique=True)
    added_at = DateTimeField()
    dkg_status = IntegerField()
    is_deleted = BooleanField(default=False)
    first_run = BooleanField(default=True)
    repair_mode = BooleanField(default=False)

    @classmethod
    def add(cls, name):
        try:
            with cls.database.atomic():
                schain = cls.create(
                    name=name,
                    added_at=datetime.datetime.now(),
                    dkg_status=DKGStatus.NOT_STARTED.value
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
    def get_statuses(cls, all=False):
        if all:
            records = cls.select()
        else:
            records = cls.select().where(cls.is_deleted == False)  # noqa: E712
        dkg_statuses = []
        for record in records:
            dkg_statuses.append(cls.to_dict(record))
        return dkg_statuses

    @classmethod
    def to_dict(cls, record):
        return {
            'name': record.name,
            'added_at': record.added_at.timestamp(),
            'dkg_status': record.dkg_status,
            'dkg_status_name': DKGStatus(record.dkg_status).name,
            'is_deleted': record.is_deleted,
            'first_run': record.first_run
        }

    def dkg_started(self):
        self.set_dkg_status(DKGStatus.IN_PROGRESS)

    def dkg_failed(self):
        self.set_dkg_status(DKGStatus.FAILED)

    def dkg_done(self):
        self.set_dkg_status(DKGStatus.DONE)

    def set_dkg_status(self, val):
        logger.info(f'Changing DKG status for {self.name} to {val.name}')
        self.dkg_status = val.value
        self.save()

    def set_deleted(self):
        self.is_deleted = True
        self.save()

    def set_first_run(self, val):
        logger.info(f'Changing first_run for {self.name} to {val}')
        self.first_run = val
        self.save()

    def set_repair_mode(self, value):
        logger.info(f'Changing repair_mode for {self.name} to {value}')
        self.repair_mode = value
        self.save()


def create_tables():
    logger.info('Creating schainrecord table...')
    if not SChainRecord.table_exists():
        SChainRecord.create_table()


def set_schains_first_run():
    logger.info('Setting first_run=True for all sChain records')
    query = SChainRecord.update(first_run=True).where(
        SChainRecord.first_run == False)  # noqa
    query.execute()


def upsert_schain_record(name):
    if not SChainRecord.added(name):
        schain_record, _ = SChainRecord.add(name)
    else:
        schain_record = SChainRecord.get_by_name(name)
    return schain_record


def mark_schain_deleted(name):
    if SChainRecord.added(name):
        schain_record = SChainRecord.get_by_name(name)
        schain_record.set_deleted()


def toggle_schain_repair_mode(name):
    logger.info(f'Toggling repair mode for schain {name}')
    query = SChainRecord.update(repair_mode=True).where(
        SChainRecord.name == name)
    count = query.execute()
    return count > 0
