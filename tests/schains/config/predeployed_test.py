from marionette_predeployed import MARIONETTE_ADDRESS
from etherbase_predeployed import ETHERBASE_ADDRESS
from context_predeployed import CONTEXT_ADDRESS
from skale.dataclasses.schain_options import AllocationType

from core.schains.types import SchainType
from core.schains.config.predeployed import (
    generate_v1_predeployed_contracts, generate_predeployed_accounts
)
from tools.configs.schains import ETHERBASE_ALLOC


NUM_OF_PREDEPLOYED_CONTRACTS_GEN_0 = 22
NUM_OF_PREDEPLOYED_CONTRACTS_GEN_1 = 33


def test_generate_predeployed_accounts():
    predeployed_section = generate_predeployed_accounts(
        schain_name='abc',
        schain_type=SchainType.medium,
        allocation_type=AllocationType.DEFAULT,
        schain_nodes={},
        on_chain_owner='0xD1000000000000000000000000000000000000D1',
        mainnet_owner='0xD4000000000000000000000000000000000000D4',
        originator_address='0xD500000000000000000000000000000000D5',
        generation=0
    )
    assert len(predeployed_section.keys()) == NUM_OF_PREDEPLOYED_CONTRACTS_GEN_0

    predeployed_section = generate_predeployed_accounts(
        schain_name='abc',
        schain_type=SchainType.medium,
        allocation_type=AllocationType.DEFAULT,
        schain_nodes={},
        on_chain_owner='0xD1000000000000000000000000000000000000D1',
        mainnet_owner='0xD4000000000000000000000000000000000000D4',
        originator_address='0xD1000000000000000000000000000000000000D1',
        generation=1
    )
    assert len(predeployed_section.keys()) == NUM_OF_PREDEPLOYED_CONTRACTS_GEN_1


def test_generate_v1_predeployed_contracts():
    v1_precompiled_contracts = generate_v1_predeployed_contracts(
        schain_type=SchainType.medium,
        allocation_type=AllocationType.DEFAULT,
        on_chain_owner=MARIONETTE_ADDRESS,
        mainnet_owner='0x0123456789Ab',
        message_proxy_for_schain_address='0x987654321fC',
        originator_address='0xD500000000000000000000000000000000D5',
        schain_name='test'
    )
    assert len(v1_precompiled_contracts.keys()) == 11
    assert v1_precompiled_contracts.get('0xD1000000000000000000000000000000000000D1')
    assert v1_precompiled_contracts.get('0xd2bA3e0000000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xd2Ba3ED200000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xD2c0DeFACe000000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xd2c0defaCeD20000000000000000000000000000')
    assert v1_precompiled_contracts.get('0xD3002000000000000000000000000000000000d3')
    assert v1_precompiled_contracts.get(CONTEXT_ADDRESS)

    etherbase_balance = v1_precompiled_contracts[ETHERBASE_ADDRESS]['balance']
    assert etherbase_balance == hex(ETHERBASE_ALLOC)
