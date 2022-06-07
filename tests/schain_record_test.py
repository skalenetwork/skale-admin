from web.models.schain import SChainRecord


def test_ssl_change_date_matches_no_certs(schain_db, ssl_folder):
    schain_record = SChainRecord.get_by_name(schain_db)
    assert not schain_record.ssl_reload_needed()


def test_ssl_change_date_matches(schain_db, cert_key_pair):
    schain_record = SChainRecord.get_by_name(schain_db)

    assert schain_record.ssl_reload_needed()
    schain_record.ssl_reloaded()
    assert not schain_record.ssl_reload_needed()
