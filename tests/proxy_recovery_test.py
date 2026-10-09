from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from core.monitor.fair.action_skaled import FairSkaledActionManager
from tools.constants.fair import SKALED_RESTART_JOB_NAME


def test_restart_keeps_earliest_deadline():
    scheduler = BackgroundScheduler()
    scheduler.start(paused=True)
    record = SimpleNamespace(restart_ts=0)
    record.set_restart_ts = lambda ts: setattr(record, 'restart_ts', ts)
    manager = SimpleNamespace(
        scheduler=scheduler, chain_record=record, recreated_skaled_container=lambda: None
    )
    schedule = FairSkaledActionManager.schedule_skaled_restart.__wrapped__
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        with (
            mock.patch('core.monitor.fair.action_skaled.time.time', return_value=now),
            mock.patch(
                'core.monitor.fair.action_skaled.random_timestamp_between',
                side_effect=lambda start, end: end,
            ),
        ):
            assert schedule(manager, now + 3900)
            assert record.restart_ts == now + 3600
            assert not schedule(manager, now + 4000)
            assert schedule(manager, now + 900)
            assert record.restart_ts == now + 600
            assert not schedule(manager, now + 900)
            assert schedule(manager, now - 10)
            assert record.restart_ts == now
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == SKALED_RESTART_JOB_NAME
            assert jobs[0].misfire_grace_time is None
            assert jobs[0].next_run_time.timestamp() == now
    finally:
        scheduler.shutdown()


def test_restart_record_is_preserved_when_scheduling_fails():
    manager = SimpleNamespace(
        scheduler=mock.Mock(), chain_record=mock.Mock(), recreated_skaled_container=mock.Mock()
    )
    manager.scheduler.get_job.return_value = None
    manager.scheduler.add_job.side_effect = RuntimeError('scheduler unavailable')
    with pytest.raises(RuntimeError, match='scheduler unavailable'):
        FairSkaledActionManager.schedule_skaled_restart.__wrapped__(manager, 0)
    assert manager.chain_record.set_restart_ts.call_args == mock.call(
        manager.chain_record.restart_ts
    )
