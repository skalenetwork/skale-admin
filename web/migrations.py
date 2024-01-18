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
from peewee import DateTimeField, IntegerField, BooleanField, CharField

from web.models.schain import DEFAULT_CONFIG_VERSION
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
    # 1.0 -> 1.2 update fields
    add_new_schain_field(db, migrator)
    add_repair_mode_field(db, migrator)
    add_needs_reload_field(db, migrator)

    # 1.2 -> 2.0 update fields
    add_monitor_last_seen_field(db, migrator)
    add_monitor_id_field(db, migrator)
    add_config_version_field(db, migrator)

    # 2.0 -> 2.1 update fields
    add_restart_count_field(db, migrator)
    add_failed_rpc_count_field(db, migrator)

    # 2.3 -> 2.4 update fields
    add_failed_snapshot_from(db, migrator)

    # 2.4 -> 2.5 update fields
    add_backup_run_field(db, migrator)
    add_sync_config_run_field(db, migrator)


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


def add_monitor_last_seen_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'monitor_last_seen',
        DateTimeField(null=True)
    )


def add_monitor_id_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'monitor_id',
        IntegerField(default=0)
    )


def add_config_version_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'config_version',
        CharField(default=DEFAULT_CONFIG_VERSION)
    )


def add_restart_count_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'restart_count',
        IntegerField(default=0)
    )


def add_failed_rpc_count_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'failed_rpc_count',
        IntegerField(default=0)
    )


def add_failed_snapshot_from(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'snapshot_from',
        CharField(default='')
    )


def add_backup_run_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'backup_run',
        BooleanField(default=False)
    )


def add_sync_config_run_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'sync_config_run',
        BooleanField(default=False)
    )


def add_dkg_step_field(db, migrator):
    add_column(
        db, migrator, 'SChainRecord', 'dkg_step',
        IntegerField(default=0)
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
