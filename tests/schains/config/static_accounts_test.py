from core.schains.config.legacy_data import is_static_accounts, static_accounts, static_groups

SCHAIN_NAME = 'test'


def test_is_static_accounts():
    assert is_static_accounts(SCHAIN_NAME)
    assert not is_static_accounts('qwerty')


def test_static_accounts():
    accounts = static_accounts(SCHAIN_NAME)
    assert isinstance(accounts, dict)
    assert accounts.get('accounts', None)


def test_static_groups():
    assert static_groups(SCHAIN_NAME)
    assert static_groups('not-exists') == {}
