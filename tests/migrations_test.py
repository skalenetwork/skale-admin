import pytest
from peewee import CharField, Model, SqliteDatabase
from playhouse.migrate import SqliteMigrator

from tools.configs.db import DB_PRAGMAS
from web.migrations import add_new_schain_field, add_repair_mode_field


TEST_DB_FILE = 'test-skale.db'
TEST_TABLE = 'test'


@pytest.fixture
def test_db():
    db = SqliteDatabase(TEST_DB_FILE, DB_PRAGMAS)

    class BaseModel(Model):
        database = db

        class Meta:
            database = db

    class TestModel(BaseModel):
        name = CharField(unique=True)

    TestModel.create_table()
    yield db


@pytest.fixture
def migrator(test_db):
    return SqliteMigrator(test_db)


def test_add_new_schain_field(test_db, migrator):
    add_new_schain_field(test_db, migrator)
    assert test_db.table_exists('TestTable')


def test_add_repair_mode_field(test_db, migrator):
    add_repair_mode_field(test_db, migrator)
    assert test_db.table_exists('TestTable')
