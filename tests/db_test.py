from concurrent.futures import ProcessPoolExecutor as pexec

import pytest

from web.models.schain import (
    get_schains_names,
    get_schains_statuses,
    mark_schain_deleted,
    set_schains_first_run,
    switch_off_repair_mode,
    toggle_schain_repair_mode,
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


def test_toggle_repair_mode(db, upsert_db):
    result = toggle_schain_repair_mode('schain-0')
    assert result
    assert SChainRecord.select().where(
        SChainRecord.repair_mode == True).count() == 1  # noqa: E712
    cursor = SChainRecord.select().where(
        SChainRecord.repair_mode == True).execute()  # noqa: E712
    records = list(cursor)
    assert len(records) == 1
    assert records[0].name == 'schain-0'
    assert records[0].snapshot_from == ''

    result = toggle_schain_repair_mode('schain-0', '1.1.1.1')
    cursor = SChainRecord.select().where(
        SChainRecord.repair_mode == True).execute()  # noqa: E712
    records = list(cursor)
    assert len(records) == 1
    assert records[0].name == 'schain-0'
    assert records[0].snapshot_from == '1.1.1.1'

    switch_off_repair_mode('schain-0')
    assert SChainRecord.select().where(
        SChainRecord.repair_mode == True).count() == 0  # noqa: E712
    cursor = SChainRecord.select().where(
        SChainRecord.name == 'schain-0').execute()  # noqa: E712
    records = list(cursor)
    assert records[0].name == 'schain-0'
    assert not records[0].repair_mode
    assert records[0].snapshot_from == ''


def test_toggle_repair_mode_schain_not_exists(db, upsert_db):
    result = toggle_schain_repair_mode('undefined-schain')
    assert not result
    assert SChainRecord.select().where(
        SChainRecord.repair_mode == True).count() == 0  # noqa: E712


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
