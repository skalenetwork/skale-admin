from core.schains.config.helper import calculate_deployment_owner_slot


def test_calculate_deployment_owner_slot():
    owner = '0x5B38Da6a701c568545dCfcB03FcB875f56beddC4'
    slot = calculate_deployment_owner_slot(owner)
    assert slot == '0x1a8bdcd502c88e7f419c7bc45ddfcbfc49fd19677ad7085b2a7eedcbdf367a69'
