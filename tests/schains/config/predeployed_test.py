from marionette_predeployed import MARIONETTE_ADDRESS

from core.schains.types import SchainType
from core.schains.config.predeployed import (
    generate_v1_precompiled_contracts, generate_predeployed_section
)


def test_generate_predeployed_section():
    predeployed_section = generate_predeployed_section(
        schain_name='abc',
        schain_type=SchainType.medium,
        schain_nodes={},
        on_chain_owner='0xD1000000000000000000000000000000000000D1',
        mainnet_owner='0xD4000000000000000000000000000000000000D4',
        generation=0
    )
    assert len(predeployed_section.keys()) == 43


def test_generate_v1_precompiled_contracts():
    v1_precompiled_contracts = generate_v1_precompiled_contracts(
        schain_type=SchainType.medium,
        on_chain_owner=MARIONETTE_ADDRESS,
        mainnet_owner='0x0123456789Ab',
        message_proxy_for_schain_address='0x987654321fC'
    )
    assert len(v1_precompiled_contracts.keys()) == 9
    assert v1_precompiled_contracts.get('0xD1000000000000000000000000000000000000D1')
    assert v1_precompiled_contracts.get('0xd2bA3e0000000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xd2Ba3ED200000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xD2c0DeFACe000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xd2c0defaCeD20000000000000000000000000000')
