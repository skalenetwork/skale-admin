from core.schains.types import SchainType
from core.schains.config.static_params import (
    get_static_schain_cmd, get_static_schain_info, get_static_node_info
)


def test_get_static_schain_cmd():
    schain_cmd = get_static_schain_cmd()
    assert schain_cmd == ['-v 3', '--web3-trace', '--enable-debug-behavior-apis', '--aa no']


def test_get_static_schain_info():
    schain_info = get_static_schain_info()
    assert schain_info == {
        "revertableFSPatchTimestamp": 1000000,
        "contractStoragePatchTimestamp": 1000000,
        "snapshotIntervalSec": 0,
        "emptyBlockIntervalMs": 10000,
        "snapshotDownloadTimeout": 18000,
        "snapshotDownloadInactiveTimeout": 120
    }


def test_get_static_node_info():
    node_info_small = get_static_node_info(SchainType.small)
    node_info_medium = get_static_node_info(SchainType.medium)

    assert node_info_small.get('logLevelConfig')
    assert node_info_small.get('minCacheSize')
    assert node_info_small.get('maxOpenLeveldbFiles')

    assert node_info_small != node_info_medium
