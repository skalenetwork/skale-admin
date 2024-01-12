import time
from core.schains.exit_scheduler import ExitScheduleFileManager

import pytest


def test_exit_schedule_fm(secret_key, schain_db):
    name = schain_db
    esfm = ExitScheduleFileManager(name)
    ts = time.time()
    with pytest.raises(FileNotFoundError):
        assert esfm.exit_ts
    esfm.exit_ts = ts
    assert esfm.exit_ts == ts
    assert esfm.exists()
    esfm.rm()
    assert not esfm.exists()
