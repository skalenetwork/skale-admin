from core.schains.status import (
    get_node_cli_status,
    node_cli_status_filepath,
    NodeCliStatus,
    SkaledStatus,
)
from core.schains.config.directory import skaled_status_filepath

CURRENT_TS = 1594903080

NCLI_STATUS_DICT = {'repair_ts': CURRENT_TS, 'snapshot_from': '127.0.0.1'}


def test_skaled_status(skaled_status, _schain_name):
    status_filepath = skaled_status_filepath(_schain_name)
    skaled_status = SkaledStatus(filepath=status_filepath)

    assert skaled_status.subsystem_running == {
        'SnapshotDownloader': False,
        'Blockchain': False,
        'Rpc': False,
    }

    assert skaled_status.exit_state == {
        'ClearDataDir': False,
        'StartAgain': False,
        'StartFromSnapshot': False,
        'ExitTimeReached': False,
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


def test_broken_status_file(skaled_status_broken_file):
    assert not skaled_status_broken_file.exit_time_reached
    assert not skaled_status_broken_file.downloading_snapshot


def test_log(skaled_status, _schain_name, caplog):
    status_filepath = skaled_status_filepath(_schain_name)
    skaled_status = SkaledStatus(filepath=status_filepath)
    skaled_status.log()


def test_node_cli_status_empty(_schain_name):
    cli_status = get_node_cli_status(_schain_name)
    assert cli_status is None

    status_filepath = node_cli_status_filepath(_schain_name)
    cli_status = NodeCliStatus(filepath=status_filepath)

    assert cli_status.repair_ts is None
    assert cli_status.snapshot_from is None


def test_node_cli_status_repair(_schain_name, ncli_status):
    cli_status = get_node_cli_status(_schain_name)

    assert cli_status.repair_ts == CURRENT_TS
    assert cli_status.snapshot_from == '127.0.0.1'
