""" SKALE data prep for testing """

import logging

from skale.utils.contracts_provision.main import (
    setup_validator, _skip_evm_time
)
from skale.utils.contracts_provision import MONTH_IN_SECONDS
from tests.utils import init_skale


logger = logging.getLogger(__name__)


def cleanup_contracts(skale):
    for schain_id in skale.schains_internal.get_all_schains_ids():
        schain_data = skale.schains.get(schain_id)
        schain_name = schain_data.get('name', None)
        if schain_name is not None:
            skale.manager.delete_schain(schain_name, wait_for=True)

    active_node_ids = skale.nodes.get_active_node_ids()
    logger.info(f'Removing {len(active_node_ids)} nodes from contracts')
    for node_id in active_node_ids:
        skale.manager.node_exit(node_id, wait_for=True)


if __name__ == "__main__":
    skale = init_skale()
    cleanup_contracts(skale)
    setup_validator(skale)
    _skip_evm_time(skale.web3, MONTH_IN_SECONDS)
