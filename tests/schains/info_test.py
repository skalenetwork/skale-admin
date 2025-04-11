import freezegun

from core.schains.info import get_schain_info_by_name
from tests.utils import CURRENT_DATETIME, upsert_schain_record_with_config

from web3 import Web3


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_schain_info_by_name(skale, schain_on_contracts, schain_db):
    name = schain_on_contracts
    schain_record = upsert_schain_record_with_config(name)
    info = get_schain_info_by_name(skale, name)
    expected_ts = int(schain_record.repair_date.timestamp())
    assert info.name == name
    assert info.schain_id == skale.schains.name_to_id(name)
    assert info.part_of_node == 1
    assert info.dkg_status == 1
    assert not info.is_deleted
    assert info.first_run
    assert info.repair_ts == expected_ts

    assert info.to_dict() == {
        'name': name,
        'id': Web3.to_hex(skale.schains.name_to_id(name)),
        'mainnet_owner': info.mainnet_owner,
        'part_of_node': 1,
        'dkg_status': 1,
        'is_deleted': False,
        'first_run': True,
        'repair_ts': expected_ts,
    }


def test_get_schain_info_by_name_not_exist_contracts(skale, schain_db):
    name = 'undefined_schain'
    info = get_schain_info_by_name(skale, name)
    assert info is None


def test_get_schain_info_by_name_not_exist_db(skale, schain_on_contracts, db):
    name = schain_on_contracts
    info = get_schain_info_by_name(skale, name)
    assert info is None
