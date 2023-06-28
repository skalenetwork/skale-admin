from core.schains.schain_eth_state import ExternalConfig, ExternalState
from tests.utils import ALLOWED_RANGES


def test_schain_mainnet_state(schain_db, secret_key):
    name = schain_db
    econfig = ExternalConfig(name=name)
    assert econfig.ranges == []
    assert econfig.ima_linked
    assert econfig.chain_id is None

    estate = ExternalState(ima_linked=False, chain_id=4, ranges=ALLOWED_RANGES)

    econfig.update(estate)
    assert econfig.ranges == ALLOWED_RANGES
    assert not econfig.ima_linked
    assert econfig.chain_id == 4
