from core.schains.info import get_schain_info_by_name
from tests.utils import upsert_schain_record_with_config


def test_get_schain_info_by_name(skale, schain_on_contracts, schain_db):
    name = schain_on_contracts
    upsert_schain_record_with_config(name)
    info = get_schain_info_by_name(skale, name)
    assert info.name == name
    assert info.schain_id == skale.schains.name_to_id(name)
    assert info.part_of_node == 1
    assert info.dkg_status == 1
    assert not info.is_deleted
    assert info.first_run
    assert not info.repair_mode

    assert info.to_dict() == {
       'name': name,
       'id': skale.schains.name_to_id(name),
       'mainnet_owner': info.mainnet_owner,
       'part_of_node': 1,
       'dkg_status': 1,
       'is_deleted': False,
       'first_run': True,
       'repair_mode': False
    }


def test_get_schain_info_by_name_not_exist_contracts(
    skale, schain_db
):
    name = 'undefined_schain'
    info = get_schain_info_by_name(skale, name)
    assert info is None


def test_get_schain_info_by_name_not_exist_db(
    skale, schain_on_contracts, db
):
    name = schain_on_contracts
    info = get_schain_info_by_name(skale, name)
    assert info is None
