from functools import wraps

from skale import SkaleManager
from skale.types.schain import SchainName

from core.dkg.utils import DkgError


def ensure_schain_exists(skale: SkaleManager, schain_name: SchainName) -> None:
    if not skale.schains_internal.is_schain_exist(schain_name):
        raise DkgError(f'sChain {schain_name} does not exist in SKALE Manager')


def require_schain_exists(func):
    @wraps(func)
    def wrapper(instance, *args, **kwargs):
        ensure_schain_exists(instance.skale, instance.chain_name)
        return func(instance, *args, **kwargs)

    return wrapper
