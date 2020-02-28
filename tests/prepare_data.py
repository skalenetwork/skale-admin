""" SKALE data prep for testing """

from tests.conftest import skale
from tests.constants import (D_VALIDATOR_MIN_DEL, D_VALIDATOR_ID, D_DELEGATION_PERIOD,
                             D_DELEGATION_INFO, D_VALIDATOR_NAME, D_VALIDATOR_DESC,
                             D_VALIDATOR_FEE)


def validator_exist(skale):
    return skale.validator_service.number_of_validators() > 0


def setup_validator(skale):
    """Create and activate a validator"""
    if not validator_exist(skale):
        create_validator(skale)
        enable_validator(skale)
    delegation_id = len(skale.delegation_service.get_all_delegations_by_validator(
        skale.wallet.address))
    set_test_msr(skale)
    delegate_to_validator(skale)
    accept_pending_delegation(skale, delegation_id)
    skip_delegation_delay(skale, delegation_id)


def link_address_to_validator(skale):
    print('Linking address to validator')
    skale.delegation_service.link_node_address(
        node_address=skale.wallet.address,
        wait_for=True
    )


def skip_delegation_delay(skale, delegation_id):
    print(f'Activating delegation with ID {delegation_id}')
    skale.token_state._skip_transition_delay(
        delegation_id,
        wait_for=True
    )


def accept_pending_delegation(skale, delegation_id):
    print(f'Accepting delegation with ID: {delegation_id}')
    skale.delegation_service.accept_pending_delegation(
        delegation_id=delegation_id,
        wait_for=True
    )


def get_test_delegation_amount(skale):
    msr = skale.constants_holder.msr()
    return msr * 10


def set_test_msr(skale):
    skale.constants_holder._set_msr(
        new_msr=D_VALIDATOR_MIN_DEL,
        wait_for=True
    )


def delegate_to_validator(skale):
    print(f'Delegating tokens to validator ID: {D_VALIDATOR_ID}')
    skale.delegation_service.delegate(
        validator_id=D_VALIDATOR_ID,
        amount=get_test_delegation_amount(skale),
        delegation_period=D_DELEGATION_PERIOD,
        info=D_DELEGATION_INFO,
        wait_for=True
    )


def enable_validator(skale):
    print(f'Enabling validator ID: {D_VALIDATOR_ID}')
    skale.validator_service._enable_validator(D_VALIDATOR_ID, wait_for=True)


def create_validator(skale):
    print('Creating default validator')
    skale.delegation_service.register_validator(
        name=D_VALIDATOR_NAME,
        description=D_VALIDATOR_DESC,
        fee_rate=D_VALIDATOR_FEE,
        min_delegation_amount=D_VALIDATOR_MIN_DEL,
        wait_for=True
    )


if __name__ == "__main__":
    skale_lib = skale()
    setup_validator(skale_lib)
