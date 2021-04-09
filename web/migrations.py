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

from playhouse.migrate import SqliteMigrator, migrate as playhouse_migrate
from peewee import BooleanField
from tools.db import get_database


logger = logging.getLogger(__name__)


def migrate():
    """ This function will include all migrations for the SQLite database
        To add a new field create a new method named `add_FIELD_NAME_field`
        to this file and run it from `run_migrations` method
    """
    db = get_database()
    migrator = SqliteMigrator(db)
    run_migrations(db, migrator)


def run_migrations(db, migrator):
    logging.info('Running migrations ...')
    add_new_schain_field(db, migrator)
    add_repair_mode_field(db, migrator)
    add_needs_reload_field(db, migrator)


def add_new_schain_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'new_schain',
        BooleanField(default=True)
    )


def add_repair_mode_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'repair_mode',
        BooleanField(default=False)
    )


def add_needs_reload_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'needs_reload',
        BooleanField(default=False)
    )


def find_column(db, table_name, column_name):
    columns = db.get_columns(table_name)
    return next((x for x in columns if x.name == column_name), None)


def add_column(db, migrator, table_name, column_name, field):
    logging.info(f'Add column: {table_name}.{column_name}')
    if not find_column(db, table_name, column_name):
        logging.info(f'Going to add: {table_name}.{column_name}')
        playhouse_migrate(
            migrator.add_column(table_name, column_name, field)
        )
