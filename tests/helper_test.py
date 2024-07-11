from tools.helper import is_address_contract, no_hyphens
from tools.configs.web3 import ZERO_ADDRESS


def test_is_address_contract(skale):
    assert not is_address_contract(skale.web3, ZERO_ADDRESS)
    assert is_address_contract(skale.web3, skale.manager.address)
    assert is_address_contract(skale.web3, skale.nodes.address)


def test_no_hyphen():
    no_hyphens('too') == 'too'
    no_hyphens('too-boo') == 'too_boo'
    no_hyphens('too-boo_goo') == 'too_boo_goo'
    no_hyphens('too_goo') == 'too_goo'
