from concurrent.futures import ProcessPoolExecutor as pexec

import pytest

from web.models.schain import (
    create_tables,
    set_schains_first_run,
    upsert_schain_record,
    mark_schain_deleted,
    SChainRecord
)


THREADS = 8
RECORDS_NUMBER = THREADS
MAX_WORKERS = 5


@pytest.fixture
def db():
    create_tables()
    yield
    SChainRecord.drop_table()


@pytest.fixture
def upsert_db(db):
    for i in range(RECORDS_NUMBER):
        upsert_schain_record(f'schain-{i}')
    return


def test_upsert_schain_record(db):
    with pexec(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(upsert_schain_record, f'schain-{i}')
            for i in range(RECORDS_NUMBER)
        ]
        for f in futures:
            f.result()

    assert SChainRecord.select().count() == RECORDS_NUMBER
    # Insert existent
    upsert_schain_record('schain-0')
    assert SChainRecord.select().count() == RECORDS_NUMBER


def test_mark_schain_deleted(db, upsert_db):
    with pexec(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(mark_schain_deleted, f'schain-{i}')
            for i in range(THREADS)
        ]
        for f in futures:
            f.result()

    assert SChainRecord.select().count() == RECORDS_NUMBER
    # Mark again
    mark_schain_deleted('schain-0')
    assert SChainRecord.select().where(
        SChainRecord.is_deleted == True).count() == RECORDS_NUMBER  # noqa: E712


def test_schains_first_run(db, upsert_db):
    set_schains_first_run()
    assert SChainRecord.select().where(
        SChainRecord.first_run == True).count() == RECORDS_NUMBER  # noqa: E712
    # Perform again
    set_schains_first_run()
    assert SChainRecord.select().where(
        SChainRecord.first_run == True).count() == RECORDS_NUMBER  # noqa: E712
