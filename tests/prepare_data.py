""" SKALE data prep for testing """

import logging

from skale.utils.helper import init_default_logger
from skale.utils.contracts_provision.main import (
    setup_validator, _skip_evm_time, create_nodes, cleanup_nodes_schains,
    add_test_permissions, add_test_schain_type
)
from skale.utils.contracts_provision import MONTH_IN_SECONDS

from core.ima.schain import update_predeployed_ima

from tests.utils import init_web3_skale


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    init_default_logger()
    skale = init_web3_skale()
    add_test_permissions(skale)
    add_test_schain_type(skale)
    cleanup_nodes_schains(skale)
    setup_validator(skale)
    _skip_evm_time(skale.web3, MONTH_IN_SECONDS)

    if skale.constants_holder.get_launch_timestamp() != 0:
        skale.constants_holder.set_launch_timestamp(0, wait_for=True)

    update_predeployed_ima()

    create_nodes(skale)
    _skip_evm_time(skale.web3, MONTH_IN_SECONDS)
