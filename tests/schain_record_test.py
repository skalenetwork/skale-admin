from web.models.schain import SChainRecord
from core.schains.ssl import update_ssl_change_date, ssl_reload_needed


def test_ssl_change_date_matches_no_certs(schain_db, ssl_folder):
    schain_record = SChainRecord.get_by_name(schain_db)
    assert not ssl_reload_needed(schain_record)


def test_ssl_change_date_matches(schain_db, cert_key_pair):
    schain_record = SChainRecord.get_by_name(schain_db)

    assert ssl_reload_needed(schain_record)
    update_ssl_change_date(schain_record)
    assert not ssl_reload_needed(schain_record)
