import json
import pytest

from core.schains.config.generator import SChainBaseConfig
from core.schains.config.accounts import generate_dynamic_accounts

from tools.helper import read_json
from tools.configs.schains import BASE_SCHAIN_CONFIG_FILEPATH

# Run only on admin 2.0.2 or older
# Add config with node groups to the root admin folder

CHAINS = ['']


@pytest.mark.skip(reason="test only used to generate static accounts for a sync node")
def test_generate_config(skale):
    for schain_name in CHAINS:

        current_config = read_json(f'{schain_name}.json')
        original_group = current_config["skaleConfig"]["sChain"]["nodeGroups"]["0"]["nodes"]

        schain = skale.schains.get_by_name(schain_name)

        schain_nodes_with_schains = []
        for key, value in original_group.items():
            schain_nodes_with_schains.append({
                'id': int(key),
                'publicKey': value[2]
            })

        base_config = SChainBaseConfig(BASE_SCHAIN_CONFIG_FILEPATH)

        print('base_config')
        print(base_config.config)
        print(base_config.config['accounts'])

        # assert False

        dynamic_accounts = generate_dynamic_accounts(
            schain=schain,
            schain_nodes=schain_nodes_with_schains
        )

        accounts = {
            **base_config.config['accounts'],
            **dynamic_accounts
        }

        with open(f'accounts/schain-{schain_name}.json', 'w') as outfile:
            json.dump({'accounts': accounts}, outfile, indent=4)
