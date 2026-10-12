import pytest

from core.dkg.schain.validation import ensure_schain_exists, require_schain_exists
from core.dkg.utils import SchainNotFoundError

NONEXISTENT_SCHAIN_NAME = 'nonexistent-chain'


class ChainStub:
    def __init__(self, skale, chain_name):
        self.skale = skale
        self.chain_name = chain_name

    @require_schain_exists
    def act(self):
        return True


def test_ensure_schain_exists_passes_for_existing_chain(skale, schain_on_contracts):
    ensure_schain_exists(skale, schain_on_contracts)


def test_ensure_schain_exists_raises_for_missing_chain(skale):
    with pytest.raises(SchainNotFoundError):
        ensure_schain_exists(skale, NONEXISTENT_SCHAIN_NAME)


def test_require_schain_exists_aborts_decorated_call(skale):
    stub = ChainStub(skale, NONEXISTENT_SCHAIN_NAME)
    with pytest.raises(SchainNotFoundError):
        stub.act()
