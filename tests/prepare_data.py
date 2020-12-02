""" SKALE data prep for testing """

import logging

from skale.utils.helper import init_default_logger
from skale.utils.contracts_provision.main import (
    setup_validator, _skip_evm_time, create_nodes, cleanup_nodes_schains
)
from skale.utils.contracts_provision import MONTH_IN_SECONDS
from tests.utils import init_skale


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    init_default_logger()
    skale = init_skale()
    cleanup_nodes_schains(skale)
    setup_validator(skale)
    _skip_evm_time(skale.web3, MONTH_IN_SECONDS)

    if skale.constants_holder.get_launch_timestamp() != 0:
        skale.constants_holder.set_launch_timestamp(0, wait_for=True)

    print('skale.wallet.address skale skale skale ->>')
    print(skale.wallet.address)

    create_nodes(skale)
    _skip_evm_time(skale.web3, MONTH_IN_SECONDS)
