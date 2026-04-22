import pytest
from eth_typing import HexStr

from tools.settings import SkaleSettings


class TestingSettings(SkaleSettings):
    eth_private_key: HexStr


@pytest.fixture(scope='session')
def st() -> TestingSettings:
    return TestingSettings()  # type: ignore[call-arg]
