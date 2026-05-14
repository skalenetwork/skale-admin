import pytest

from core.dkg.schain.utils import generate_bls_keys
from core.dkg.structures import DKGStep
from core.dkg.utils import DKGKeyGenerationError


class DKGClientMock:
    def __init__(
        self,
        public_key=None,
        bls_public_keys=None,
        bls_key_generated=False,
        fail_on_public_keys=False,
    ):
        self.chain_name = 'test-schain'
        self.public_key = public_key or ['1', '2', '3', '4']
        self.bls_public_keys = bls_public_keys or ['1:2:3:4']
        self.bls_key_generated = bls_key_generated
        self.fail_on_public_keys = fail_on_public_keys
        self.common_public_key = ['common']
        self.node_id_contract = 11
        self.node_id_dkg = 0
        self.node_ids_dkg = {0: 11}
        self.t = 1
        self.n = 1
        self.bls_name = 'BLS_KEY:test'
        self.generated = False
        self.fetched = False
        self.last_completed_step = DKGStep.NONE

    def is_bls_key_generated(self):
        return self.bls_key_generated

    def generate_bls_key(self):
        self.generated = True
        return 'encrypted-key'

    def fetch_bls_public_key(self):
        self.fetched = True

    def get_bls_public_keys(self):
        if self.fail_on_public_keys:
            raise RuntimeError('public key calculation failed')
        return self.bls_public_keys

    def get_common_bls_public_key(self):
        return self.common_public_key


def test_generate_bls_keys_normalizes_generated_public_key_list():
    dkg_client = DKGClientMock(public_key=['1', '2', '3', '4'])

    keys_data = generate_bls_keys(dkg_client)

    assert dkg_client.generated
    assert not dkg_client.fetched
    assert dkg_client.last_completed_step == DKGStep.KEY_GENERATION
    assert keys_data['public_key'] == ['1', '2', '3', '4']
    assert keys_data['bls_public_keys'] == ['1:2:3:4']


def test_generate_bls_keys_accepts_existing_string_public_key():
    dkg_client = DKGClientMock(public_key='1:2:3:4', bls_key_generated=True)

    keys_data = generate_bls_keys(dkg_client)

    assert not dkg_client.generated
    assert dkg_client.fetched
    assert dkg_client.last_completed_step == DKGStep.KEY_GENERATION
    assert keys_data['public_key'] == '1:2:3:4'


def test_generate_bls_keys_raises_on_public_key_mismatch():
    dkg_client = DKGClientMock(
        public_key=['1', '2', '3', '4'],
        bls_public_keys=['4:3:2:1'],
    )

    with pytest.raises(DKGKeyGenerationError, match='generated DKG public key mismatch'):
        generate_bls_keys(dkg_client)


def test_generate_bls_keys_wraps_key_generation_errors():
    dkg_client = DKGClientMock(fail_on_public_keys=True)

    with pytest.raises(DKGKeyGenerationError) as err:
        generate_bls_keys(dkg_client)

    assert isinstance(err.value.args[0], RuntimeError)
