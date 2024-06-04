import json

from core.schains.config.legacy_data import is_static_accounts, static_accounts, static_groups
from tests.utils import STATIC_NODE_GROUPS


SCHAIN_NAME = 'test'


def test_is_static_accounts():
    assert is_static_accounts(SCHAIN_NAME)
    assert not is_static_accounts('qwerty')


def test_static_accounts():
    accounts = static_accounts(SCHAIN_NAME)
    assert isinstance(accounts, dict)
    assert accounts.get('accounts', None)


def test_static_groups(_schain_name, static_groups_for_schain):
    groups = static_groups(_schain_name)
    for key, value in STATIC_NODE_GROUPS.items():
        assert json.dumps(groups[int(key)]) == json.dumps(value)
    assert static_groups('not-exists') == {}
