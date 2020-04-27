""" SKALE data prep for testing """

import logging

from skale.utils.contracts_provision.main import setup_validator, _skip_evm_time
from skale.utils.contracts_provision import MONTH_IN_SECONDS
from skale.wallets.web3_wallet import generate_wallet

from tests.conftest import skale

logger = logging.getLogger(__name__)


def cleanup_contracts(skale):
    for schain_id in skale.schains_data.get_all_schains_ids():
        schain_data = skale.schains_data.get(schain_id)
        schain_name = schain_data.get('name', None)
        if schain_name is not None:
            skale.manager.delete_schain(schain_name, wait_for=True)

    active_node_ids = skale.nodes_data.get_active_node_ids()
    logger.info(f'Removing {len(active_node_ids)} nodes from contracts')
    for node_id in active_node_ids:
        skale.manager.delete_node_by_root(node_id, wait_for=True)


def link_node_address(skale):
    validator_id = skale.validator_service.validator_id_by_address(
        skale.wallet.address)
    main_wallet = skale.wallet
    wallet = generate_wallet(skale.web3)
    skale.wallet = wallet
    signature = skale.validator_service.get_link_node_signature(
        validator_id=validator_id
    )
    skale.wallet = main_wallet
    skale.validator_service.link_node_address(
        node_address=wallet.address,
        signature=signature,
        wait_for=True
    )


if __name__ == "__main__":
    skale_lib = skale()
    cleanup_contracts(skale_lib)
    setup_validator(skale_lib)
    link_node_address(skale_lib)
    _skip_evm_time(skale_lib.web3, MONTH_IN_SECONDS)
