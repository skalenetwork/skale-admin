from core.schains.skaled_status import SkaledStatus, init_skaled_status

from tests.utils import TEST_SKALED_STATUS_FILEPATH


def test_skaled_status():
    skaled_status = SkaledStatus(filepath=TEST_SKALED_STATUS_FILEPATH)

    assert skaled_status.subsystem_running == {
        'SnapshotDownloader': True,
        'Blockchain': False,
        'Rpc': False
    }

    assert skaled_status.exit_state == {
        'ClearDataDir': False,
        'StartAgain': False,
        'StartFromSnapshot': False,
        'ExitTimeReached': False
    }


def test_init_skaled_status(schain_skaled_status_file):
    assert isinstance(init_skaled_status(schain_skaled_status_file), SkaledStatus)


def test_is_downloading_snapshot(skaled_status_downloading_snapshot):
    assert skaled_status_downloading_snapshot.is_downloading_snapshot
