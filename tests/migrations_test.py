import os

import pytest
from peewee import CharField, Model, SqliteDatabase
from playhouse.migrate import SqliteMigrator

from tests.utils import generate_random_name
from tools.configs.db import DB_PRAGMAS
from web.migrations import add_new_schain_field, add_repair_mode_field


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
