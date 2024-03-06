from core.schains.config.static_accounts import is_static_accounts, static_accounts

SCHAIN_NAME = 'test'


def test_is_static_accounts():
    assert is_static_accounts(SCHAIN_NAME)
    assert not is_static_accounts('qwerty')


def test_static_accounts():
    accounts = static_accounts(SCHAIN_NAME)
    assert isinstance(accounts, dict)
    assert accounts.get('accounts', None)
