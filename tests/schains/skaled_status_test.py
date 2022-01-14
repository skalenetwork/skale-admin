from core.schains.skaled_status import SkaledStatus
from core.schains.config.directory import skaled_status_filepath


def test_skaled_status(skaled_status, _schain_name):
    status_filepath = skaled_status_filepath(_schain_name)
    skaled_status = SkaledStatus(filepath=status_filepath)

    assert skaled_status.subsystem_running == {
        'SnapshotDownloader': False,
        'Blockchain': False,
        'Rpc': False
    }

    assert skaled_status.exit_state == {
        'ClearDataDir': False,
        'StartAgain': False,
        'StartFromSnapshot': False,
        'ExitTimeReached': False
    }


def test_init_skaled_status(skaled_status):
    assert isinstance(skaled_status, SkaledStatus)


def test_downloading_snapshot(skaled_status_downloading_snapshot):
    assert skaled_status_downloading_snapshot.downloading_snapshot


def test_exit_time_reached(skaled_status_exit_time_reached):
    assert skaled_status_exit_time_reached.exit_time_reached


def test_no_status_file():
    skaled_status = SkaledStatus(filepath='/skaleddd_status.json')
    assert skaled_status.subsystem_running is None
    assert skaled_status.downloading_snapshot is None
