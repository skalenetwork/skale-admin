import os
from datetime import datetime

import pytest
from peewee import CharField, Model, SqliteDatabase
from playhouse.migrate import SqliteMigrator

from tests.utils import generate_random_name
from tools.configs.db import DB_PRAGMAS
from web.migrations import (
    add_new_schain_field,
    add_repair_mode_field,
    add_failed_rpc_count_field,
    add_needs_reload_field,
    add_monitor_last_seen_field,
    add_monitor_id_field,
    add_config_version_field,
    add_restart_count_field,
    add_ssl_change_date_field
)


TEST_DB_FILE = 'test-skale.db'
TEST_TABLE = 'test'
NUMBER_OF_RECORDS = 5


@pytest.fixture
def test_db():
    db = SqliteDatabase(TEST_DB_FILE, DB_PRAGMAS)
    with db:
        yield db
    os.remove(TEST_DB_FILE)


@pytest.fixture
def model(test_db):
    class BaseModel(Model):
        database = test_db

        class Meta:
            database = test_db

    class SChainRecord(BaseModel):
        name = CharField(unique=True)

    test_db.create_tables([SChainRecord])
    yield SChainRecord
    SChainRecord.drop_table()


@pytest.fixture
def migrator(test_db):
    return SqliteMigrator(test_db)


@pytest.fixture
def upserted_db(test_db, model):
    data = [
        {'name': generate_random_name()} for i in range(NUMBER_OF_RECORDS)
    ]
    model.insert_many(data)
    yield test_db


def test_add_new_schain_field(upserted_db, migrator, model):
    add_new_schain_field(upserted_db, migrator)
    assert model.table_exists()
    for r in model.select().execute():
        assert r.new_schain is False


def test_add_repair_mode_field(upserted_db, migrator, model):
    add_repair_mode_field(upserted_db, migrator)
    assert model.table_exists()
    for r in model.select().execute():
        assert r.repair_mode is False


def test_add_needs_reload_field(upserted_db, migrator, model):
    add_needs_reload_field(upserted_db, migrator)
    assert model.table_exists()
    for r in model.select().execute():
        assert r.needs_reload is False


def test_add_monitor_last_seen_field(upserted_db, migrator, model):
    add_monitor_last_seen_field(upserted_db, migrator)
    for r in model.select().execute():
        r.monitor_last_seen is None


def test_add_monitor_id_field(upserted_db, migrator, model):
    add_monitor_id_field(upserted_db, migrator)
    for r in model.select().execute():
        r.monitor_id == 0


def test_add_config_version_field(upserted_db, migrator, model):
    add_config_version_field(upserted_db, migrator)
    for r in model.select().execute():
        r.config_version == '0.0.0'


def test_add_restart_count_field(upserted_db, migrator, model):
    add_restart_count_field(upserted_db, migrator)
    for r in model.select().execute():
        r.restart_count == 0


def test_add_failed_rpc_count_field(upserted_db, migrator, model):
    add_failed_rpc_count_field(upserted_db, migrator)
    for r in model.select().execute():
        r.restart_count == 0


def test_add_ssl_change_date_field(upserted_db, migrator, model):
    add_ssl_change_date_field(upserted_db, migrator)
    for r in model.select().execute():
        r.ssl_change_date < datetime.now()
