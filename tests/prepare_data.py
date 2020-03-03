""" SKALE data prep for testing """

from tests.conftest import skale
from skale.utils.contracts_provision.main import setup_validator


if __name__ == "__main__":
    skale_lib = skale()
    setup_validator(skale_lib)
