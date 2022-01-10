from tools.helper import is_address_contract
from tools.configs.web3 import ZERO_ADDRESS


def test_is_address_contract(skale):
    assert not is_address_contract(skale.web3, ZERO_ADDRESS)
    assert is_address_contract(skale.web3, skale.manager.address)
    assert is_address_contract(skale.web3, skale.nodes.address)
