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

import datetime
from hashlib import md5
from peewee import CharField, DateTimeField, IntegrityError

from web.models.base import BaseModel


class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    token = CharField(unique=True)
    join_date = DateTimeField()

    @classmethod
    def check_no_users(cls):
        query = cls.select()
        return query.count() == 0

    @classmethod
    def join(cls, username, password, token):
        try:
            with cls.database.atomic():
                password_hash = md5((password).encode('utf-8')).hexdigest()
                join_date = datetime.datetime.now()

                user = cls.create(
                    username=username,
                    password=password_hash,
                    token=token,
                    join_date=join_date
                )
            return user, None
        except IntegrityError as err:
            return None, err

    @classmethod
    def login(cls, username, password, user_session):
        try:
            pw_hash = md5(password.encode('utf-8')).hexdigest()
            user = User.get(
                (cls.username == username) &
                (cls.password == pw_hash))
        except cls.DoesNotExist as err:
            return False, err

        user_session.auth(user)
        return True, None

    def info(self):
        return {
            'username': self.username,
            'join_date': str(self.join_date)
        }
