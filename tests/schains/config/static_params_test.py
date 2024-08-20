from core.schains.config.helper import get_static_params
from core.schains.types import SchainType
from core.schains.config.static_params import (
    get_automatic_repair_option,
    get_schain_static_param,
    get_static_schain_cmd,
    get_static_schain_info,
    get_static_node_info,
)
from tools.configs import ENV_TYPE


TEST_SCHAIN_NAME = 'test-schain'
TS_FOR_ALL_NAME = 'revertableFSPatchTimestamp'
TS_BY_CHAIN_NAME = 'flexibleDeploymentPatchTimestamp'


def test_get_static_schain_cmd():
    schain_cmd = get_static_schain_cmd()
    assert schain_cmd == ['-v 3', '--web3-trace', '--enable-debug-behavior-apis', '--aa no']


def test_get_static_schain_info():
    schain_info = get_static_schain_info(TEST_SCHAIN_NAME)
    assert schain_info == {
        'contractStorageZeroValuePatchTimestamp': 1000000,
        'revertableFSPatchTimestamp': 1000000,
        'contractStoragePatchTimestamp': 1000000,
        'verifyDaSigsPatchTimestamp': 1000000,
        'storageDestructionPatchTimestamp': 1000000,
        'powCheckPatchTimestamp': 1000000,
        'skipInvalidTransactionsPatchTimestamp': 1000000,
        'pushZeroPatchTimestamp': 1712142000,
        'precompiledConfigPatchTimestamp': 1712314800,
        'correctForkInPowPatchTimestamp': 1711969200,
        'EIP1559TransactionsPatchTimestamp': 0,
        'fastConsensusPatchTimestamp': 0,
        'flexibleDeploymentPatchTimestamp': 1723460400,
        'verifyBlsSyncPatchTimestamp': 0,
        'snapshotIntervalSec': 3600,
        'emptyBlockIntervalMs': 10000,
        'snapshotDownloadTimeout': 18000,
        'snapshotDownloadInactiveTimeout': 120,
    }


def test_get_static_schain_info_custom_chain_ts():
    custom_schain_info = get_static_schain_info(TEST_SCHAIN_NAME)
    default_schain_info = get_static_schain_info('test')

    assert custom_schain_info[TS_FOR_ALL_NAME] == default_schain_info[TS_FOR_ALL_NAME]
    assert custom_schain_info[TS_BY_CHAIN_NAME] != default_schain_info[TS_BY_CHAIN_NAME]

    assert custom_schain_info[TS_BY_CHAIN_NAME] == 1723460400
    assert default_schain_info[TS_BY_CHAIN_NAME] == 0


def test_get_schain_static_param():
    static_params = get_static_params(ENV_TYPE)
    legacy_ts_info = get_schain_static_param(
        static_params['schain'][TS_FOR_ALL_NAME], TEST_SCHAIN_NAME
    )
    assert legacy_ts_info == static_params['schain'].get(TS_FOR_ALL_NAME)
    print(static_params['schain'])

    new_ts_info_custom_chain = get_schain_static_param(
        static_params['schain'][TS_BY_CHAIN_NAME], TEST_SCHAIN_NAME
    )

    assert new_ts_info_custom_chain != static_params['schain'][TS_BY_CHAIN_NAME]
    assert new_ts_info_custom_chain == static_params['schain'][TS_BY_CHAIN_NAME][TEST_SCHAIN_NAME]

    new_ts_info_default_chain = get_schain_static_param(
        static_params['schain'][TS_BY_CHAIN_NAME], 'test'
    )
    assert new_ts_info_default_chain != static_params['schain'][TS_BY_CHAIN_NAME]
    assert new_ts_info_default_chain != static_params['schain'][TS_BY_CHAIN_NAME].get('test')
    assert new_ts_info_default_chain == static_params['schain'][TS_BY_CHAIN_NAME].get('default')


def test_get_static_node_info():
    node_info_small = get_static_node_info(SchainType.small)
    node_info_medium = get_static_node_info(SchainType.medium)

    assert node_info_small.get('logLevelConfig')
    assert node_info_small.get('minCacheSize')
    assert node_info_small.get('maxOpenLeveldbFiles')

    assert node_info_small != node_info_medium


def test_get_automatic_repair_option():
    assert get_automatic_repair_option()
    assert get_automatic_repair_option(env_type='mainnet')
    assert get_automatic_repair_option(env_type='testnet')
    assert get_automatic_repair_option(env_type='devnet')
    assert not get_automatic_repair_option(env_type='qanet')
