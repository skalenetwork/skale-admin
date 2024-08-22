import json
import pytest
from skale.schain_config.rotation_history import get_previous_schain_groups

from core.schains.config.predeployed import generate_predeployed_accounts
from core.schains.config.precompiled import generate_precompiled_accounts

from core.schains.limits import get_schain_type
from core.schains.config.generator import (
    get_on_chain_owner, get_schain_originator, SChainBaseConfig)

from tools.helper import is_address_contract
from tools.configs.schains import BASE_SCHAIN_CONFIG_FILEPATH


CHAINS = []


@pytest.mark.skip(reason="test only used to generate static accounts for a sync node")
def test_generate_config(skale):
    for schain_name in CHAINS:

        schain = skale.schains.get_by_name(schain_name)
        schain_type = get_schain_type(schain['partOfNode'])

        node_groups = get_previous_schain_groups(skale, schain_name)
        original_group = node_groups[0]['nodes']

        schain_nodes_with_schains = []
        for key, value in original_group.items():
            schain_nodes_with_schains.append({
                'id': int(key),
                'publicKey': value[2]
            })

        is_owner_contract = is_address_contract(skale.web3, schain['mainnetOwner'])
        on_chain_owner = get_on_chain_owner(schain, schain['generation'], is_owner_contract)

        mainnet_owner = schain['mainnetOwner']

        originator_address = get_schain_originator(schain)

        precompiled_accounts = generate_precompiled_accounts(
            on_chain_owner=on_chain_owner
        )

        base_config = SChainBaseConfig(BASE_SCHAIN_CONFIG_FILEPATH)

        predeployed_accounts = generate_predeployed_accounts(
            schain_name=schain['name'],
            allocation_type='default',
            schain_type=schain_type,
            schain_nodes=schain_nodes_with_schains,
            on_chain_owner=on_chain_owner,
            mainnet_owner=mainnet_owner,
            originator_address=originator_address,
            generation=schain['generation']
        )

        accounts = {
            **base_config.config['accounts'],
            **predeployed_accounts,
            **precompiled_accounts,
        }
        with open(f'accounts/schain-{schain_name}.json', 'w') as outfile:
            json.dump({'accounts': accounts}, outfile, indent=4)
