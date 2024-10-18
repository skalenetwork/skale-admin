import pytest
from tools.configs import CONFIG_FOLDER
from tests.schain_allocation import generate_schain_allocation

EXPECTED_SCHAIN_ALLOCATION = [
    (
        'mainnet',
        'medium',
        'default',
        {
            'max_consensus_storage_bytes': 63269997772,
            'max_file_storage_bytes': 63269997772,
            'max_reserved_storage_bytes': 21089999257,
            'max_skaled_leveldb_storage_bytes': 63269997772,
        },
    ),
    (
        'mainnet',
        'medium',
        'no_filestorage',
        {
            'max_consensus_storage_bytes': 94904996659,
            'max_file_storage_bytes': 0,
            'max_reserved_storage_bytes': 21089999257,
            'max_skaled_leveldb_storage_bytes': 94904996659,
        },
    ),
    (
        'mainnet',
        'medium',
        'max_contract_storage',
        {
            'max_consensus_storage_bytes': 28471498997,
            'max_file_storage_bytes': 0,
            'max_reserved_storage_bytes': 21089999257,
            'max_skaled_leveldb_storage_bytes': 161338494320,
        },
    ),
    (
        'mainnet',
        'medium',
        'max_consensus_db',
        {
            'max_consensus_storage_bytes': 151847994654,
            'max_file_storage_bytes': 0,
            'max_reserved_storage_bytes': 21089999257,
            'max_skaled_leveldb_storage_bytes': 37961998663,
        },
    ),
    (
        'mainnet',
        'medium',
        'max_filestorage',
        {
            'max_consensus_storage_bytes': 28471498997,
            'max_file_storage_bytes': 132866995322,
            'max_reserved_storage_bytes': 21089999257,
            'max_skaled_leveldb_storage_bytes': 28471498997,
        },
    ),
]


EXPECTED_LEVELDB_ALLOCATION = [
    (
        'mainnet',
        'medium',
        'default',
        {'contract_storage': 37961998663, 'db_storage': 12653999554},
    ),
    (
        'mainnet',
        'medium',
        'no_filestorage',
        {'contract_storage': 56942997995, 'db_storage': 18980999331},
    ),
    (
        'mainnet',
        'medium',
        'max_contract_storage',
        {'contract_storage': 96803096592, 'db_storage': 32267698864},
    ),
    (
        'mainnet',
        'medium',
        'max_consensus_db',
        {'contract_storage': 22777199197, 'db_storage': 7592399732},
    ),
    (
        'mainnet',
        'medium',
        'max_filestorage',
        {'contract_storage': 17082899398, 'db_storage': 5694299799},
    ),
]


@pytest.fixture(scope='module')
def schain_allocation():
    return generate_schain_allocation(CONFIG_FOLDER)


@pytest.mark.parametrize(
    'network_type,size_name,allocation_type,expected', EXPECTED_SCHAIN_ALLOCATION
)
def test_schain_allocation(network_type, size_name, allocation_type, expected, schain_allocation):
    volume_limits = schain_allocation[network_type]['volume_limits']
    assert volume_limits[size_name][allocation_type] == expected


@pytest.mark.parametrize(
    'network_type,size_name,allocation_type,expected', EXPECTED_LEVELDB_ALLOCATION
)
def test_leveldb_allocation(network_type, size_name, allocation_type, expected, schain_allocation):
    leveldb_limits = schain_allocation[network_type]['leveldb_limits']
    assert leveldb_limits[size_name][allocation_type] == expected


def test_schain_allocation_testnet(schain_allocation):
    allocation = schain_allocation
    assert allocation['qanet']['volume_limits'] == allocation['testnet']['volume_limits']
    assert allocation['qanet']['leveldb_limits'] == allocation['testnet']['leveldb_limits']
