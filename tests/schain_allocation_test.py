from tools.configs import CONFIG_FOLDER
from tools.schain_allocation import generate_schain_allocation


def test_schain_allocation():
    allocation = generate_schain_allocation(CONFIG_FOLDER)

    # devnet
    volume_limits = allocation['devnet']['volume_limits']
    assert volume_limits['large'] == {
        'max_consensus_storage_bytes': 21311992627,
        'max_file_storage_bytes': 21311992627,
        'max_reserved_storage_bytes': 7103997542,
        'max_skaled_leveldb_storage_bytes': 21311992627,
    }

    assert volume_limits['medium'] == {
        'max_consensus_storage_bytes': 2663999078,
        'max_file_storage_bytes': 2663999078,
        'max_reserved_storage_bytes': 887999692,
        'max_skaled_leveldb_storage_bytes': 2663999078,
    }
    assert volume_limits['small'] == {
        'max_consensus_storage_bytes': 166499942,
        'max_file_storage_bytes': 166499942,
        'max_reserved_storage_bytes': 55499980,
        'max_skaled_leveldb_storage_bytes': 166499942,
    }
    assert volume_limits['test'] == {
        'max_consensus_storage_bytes': 2663999078,
        'max_file_storage_bytes': 2663999078,
        'max_reserved_storage_bytes': 887999692,
        'max_skaled_leveldb_storage_bytes': 2663999078,
    }
    assert volume_limits['test4'] == {
        'max_consensus_storage_bytes': 2663999078,
        'max_file_storage_bytes': 2663999078,
        'max_reserved_storage_bytes': 887999692,
        'max_skaled_leveldb_storage_bytes': 2663999078,
    }

    # mainnet
    volume_limits = allocation['mainnet']['volume_limits']
    assert volume_limits['large'] == {
        'max_consensus_storage_bytes': 506159982182,
        'max_file_storage_bytes': 506159982182,
        'max_reserved_storage_bytes': 168719994060,
        'max_skaled_leveldb_storage_bytes': 506159982182,
    }

    assert volume_limits['medium'] == {
        'max_consensus_storage_bytes': 63269997772,
        'max_file_storage_bytes': 63269997772,
        'max_reserved_storage_bytes': 21089999257,
        'max_skaled_leveldb_storage_bytes': 63269997772,
    }
    assert volume_limits['small'] == {
        'max_consensus_storage_bytes': 3954374860,
        'max_file_storage_bytes': 3954374860,
        'max_reserved_storage_bytes': 1318124953,
        'max_skaled_leveldb_storage_bytes': 3954374860,
    }
    assert volume_limits['test'] == {
        'max_consensus_storage_bytes': 63269997772,
        'max_file_storage_bytes': 63269997772,
        'max_reserved_storage_bytes': 21089999257,
        'max_skaled_leveldb_storage_bytes': 63269997772,
    }
    assert volume_limits['test4'] == {
        'max_consensus_storage_bytes': 63269997772,
        'max_file_storage_bytes': 63269997772,
        'max_reserved_storage_bytes': 21089999257,
        'max_skaled_leveldb_storage_bytes': 63269997772,
    }

    # testnet
    volume_limits = allocation['testnet']['volume_limits']
    assert volume_limits['large'] == {
        'max_consensus_storage_bytes': 53279981568,
        'max_file_storage_bytes': 53279981568,
        'max_reserved_storage_bytes': 17759993856,
        'max_skaled_leveldb_storage_bytes': 53279981568,
    }
    assert volume_limits['medium'] == {
        'max_consensus_storage_bytes': 6659997696,
        'max_file_storage_bytes': 6659997696,
        'max_reserved_storage_bytes': 2219999232,
        'max_skaled_leveldb_storage_bytes': 6659997696,
    }
    assert volume_limits['small'] == {
        'max_consensus_storage_bytes': 416249856,
        'max_file_storage_bytes': 416249856,
        'max_reserved_storage_bytes': 138749952,
        'max_skaled_leveldb_storage_bytes': 416249856,
    }
    assert volume_limits['test'] == {
        'max_consensus_storage_bytes': 6659997696,
        'max_file_storage_bytes': 6659997696,
        'max_reserved_storage_bytes': 2219999232,
        'max_skaled_leveldb_storage_bytes': 6659997696,
    }
    assert volume_limits['test4'] == {
        'max_consensus_storage_bytes': 6659997696,
        'max_file_storage_bytes': 6659997696,
        'max_reserved_storage_bytes': 2219999232,
        'max_skaled_leveldb_storage_bytes': 6659997696,
    }

    assert allocation['qanet']['volume_limits'] == allocation['testnet']['volume_limits']
