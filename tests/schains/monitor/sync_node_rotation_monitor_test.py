import time
import logging

from skale.schain_config.generator import get_nodes_for_schain
from sync.main import _is_sync_rotation_mode

from tests.schains.monitor.main_test import SChainChecksMock
from tests.utils import get_test_rule_controller, upsert_schain_record_with_config

logger = logging.getLogger(__name__)


def test_is_sync_rotation_mode(
    schain_db,
    skale,
    schain_on_contracts,
    node_config,
    dutils,
    predeployed_ima
):
    schain_name = schain_on_contracts
    nodes = get_nodes_for_schain(skale, schain_name)

    rc = get_test_rule_controller(name=schain_name)
    node_config.id = nodes[0]['id']

    schain_record = upsert_schain_record_with_config(schain_name)
    schain_checks = SChainChecksMock(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rc,
        sync_node=True,
        dutils=dutils
    )

    finish_ts = 111
    assert not _is_sync_rotation_mode(schain_checks, finish_ts)

    finish_ts = time.time()
    assert _is_sync_rotation_mode(schain_checks, finish_ts)
