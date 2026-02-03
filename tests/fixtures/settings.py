import pytest
from eth_typing import HexStr

from tools.settings import SkaleSettings


class TestSettings(SkaleSettings):
    eth_private_key: HexStr


@pytest.fixture(scope='session')
def st() -> TestSettings:
    return TestSettings()  # type: ignore[call-arg]
