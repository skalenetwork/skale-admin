import os
import shutil
import time
from pathlib import Path

import pytest

from core.schains.process import ProcessReport

from tools.configs.schains import SCHAINS_DIR_PATH


@pytest.fixture
def tmp_dir(_schain_name):
    path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_process_report(_schain_name, tmp_dir):
    report = ProcessReport(_schain_name)
    with pytest.raises(FileNotFoundError):
        assert report.ts == 0

    ts = int(time.time())
    pid = 10
    report.update(pid=pid, ts=ts)
    assert report.ts == ts
    assert report.pid == pid
