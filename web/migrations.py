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

# This file will include all migrations for the SQLite database
# To add a new field create a new method named `add_FIELD_NAME_field` to this file and invoke it
# the `run_migrations` method

import logging

from playhouse.migrate import SqliteMigrator, migrate
from peewee import BooleanField
from tools.db import get_database


logger = logging.getLogger(__name__)


def run_migrations():
    logging.info('Running migrations...')
    db = get_database()
    migrator = SqliteMigrator(db)
    add_new_schain_field(db, migrator)


def add_new_schain_field(db, migrator):
    add_column(db, migrator, 'SChainRecord', 'new_schain', BooleanField(default=True))


def find_column(db, table_name, column_name):
    columns = db.get_columns(table_name)
    return next((x for x in columns if x.name == column_name), None)


def add_column(db, migrator, table_name, column_name, field):
    logging.info(f'Add column: {table_name}.{column_name}')
    if not find_column(db, table_name, column_name):
        logging.info(f'Going to add: {table_name}.{column_name}')
        migrate(
            migrator.add_column(table_name, column_name, field)
        )
