from core.schains.config.precompiled import generate_precompiled_accounts
from marionette_predeployed import MARIONETTE_ADDRESS
from filestorage_predeployed import FILESTORAGE_ADDRESS


def test_generate_precompiled_accounts():
    precompiled_accounts = generate_precompiled_accounts(MARIONETTE_ADDRESS)

    print_eth_contract = precompiled_accounts["0x0000000000000000000000000000000000000019"]
    assert print_eth_contract["precompiled"]["restrictAccess"] == [
        MARIONETTE_ADDRESS
    ]

    fs_contract = precompiled_accounts["0x0000000000000000000000000000000000000011"]
    assert fs_contract["precompiled"]["restrictAccess"] == [
        FILESTORAGE_ADDRESS
    ]
