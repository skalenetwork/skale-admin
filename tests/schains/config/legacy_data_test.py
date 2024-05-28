import os
import shutil

import pytest

from core.schains.config.legacy_data import is_static_accounts, static_accounts, static_groups
from tools.configs import ENV_TYPE, STATIC_GROUPS_FOLDER
from tools.helper import write_json


SCHAIN_NAME = 'test'

STATIC_NODE_GROUPS = {
    '1': {
        "rotation": {
            "leaving_node_id": 3,
            "new_node_id": 4,
        },
        "nodes": {
            "0": [
                0,
                159,
                "0xgd"
            ],
            "4": [
                4,
                31,
                "0x5d"
            ],
        },
        "finish_ts": None,
        "bls_public_key": None
    },
    '0': {
        "rotation": {
            "leaving_node_id": 2,
            "new_node_id": 3,
        },
        "nodes": {
            "0": [
                0,
                159,
                "0xgd"
            ],
            "3": [
                7,
                61,
                "0xbh"
            ],
        },
        "finish_ts": 1681390775,
        "bls_public_key": {
            "blsPublicKey0": "3",
            "blsPublicKey1": "4",
            "blsPublicKey2": "7",
            "blsPublicKey3": "9"
        }
    }
}


@pytest.fixture
def groups_for_chain():
    parent_folder = os.path.join(STATIC_GROUPS_FOLDER, ENV_TYPE)
    os.makedirs(parent_folder)
    static_groups_env_path = os.path.join(parent_folder, os.path.join(f'schain-{SCHAIN_NAME}.json'))
    try:
        yield write_json(static_groups_env_path, STATIC_NODE_GROUPS)
    finally:
        shutil.rmtree(STATIC_GROUPS_FOLDER, ignore_errors=True)


def test_is_static_accounts():
    assert is_static_accounts(SCHAIN_NAME)
    assert not is_static_accounts('qwerty')


def test_static_accounts():
    accounts = static_accounts(SCHAIN_NAME)
    assert isinstance(accounts, dict)
    assert accounts.get('accounts', None)


def test_static_groups(groups_for_chain):
    assert static_groups(SCHAIN_NAME) == STATIC_NODE_GROUPS
    assert static_groups('not-exists') == {}
