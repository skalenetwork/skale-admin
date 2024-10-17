from concurrent.futures import as_completed, ProcessPoolExecutor as pexec

import pytest

from web.models.schain import (
    get_schains_names,
    get_schains_statuses,
    mark_schain_deleted,
    set_schains_first_run,
    SChainRecord,
    upsert_schain_record
)


THREADS = 8
RECORDS_NUMBER = THREADS
MAX_WORKERS = 5


@pytest.fixture
def upsert_db(db):
    """ Fixture: db with filled records """
    for i in range(RECORDS_NUMBER):
        upsert_schain_record(f'schain-{i}')


def test_upsert_schain_record(db):
    with pexec(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(upsert_schain_record, f'schain-{i}')
            for i in range(RECORDS_NUMBER)
        ]
        for f in as_completed(futures):
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


def test_get_schains_names(db, upsert_db):
    mark_schain_deleted('schain-0')
    result = get_schains_names()
    assert result == ['schain-1', 'schain-2', 'schain-3', 'schain-4',
                      'schain-5', 'schain-6', 'schain-7']
    result = get_schains_names(include_deleted=True)
    assert result == ['schain-0',
                      'schain-1', 'schain-2', 'schain-3', 'schain-4',
                      'schain-5', 'schain-6', 'schain-7']


def test_get_schains_statuses(db, upsert_db):
    mark_schain_deleted('schain-0')
    assert len(get_schains_statuses()) == 7
    assert len(get_schains_statuses(include_deleted=True)) == 8
