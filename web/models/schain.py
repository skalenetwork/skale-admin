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
from peewee import CharField, DateTimeField, IntegrityError, IntegerField

from core.schains.dkg_status import DKGStatus
from web.models.base import BaseModel

logger = logging.getLogger(__name__)


class SChainRecord(BaseModel):
    name = CharField(unique=True)
    added_at = DateTimeField()
    dkg_status = IntegerField()

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
    def all(cls):
        records = cls.select()
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
