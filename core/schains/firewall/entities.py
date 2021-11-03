from collections import namedtuple
from skale import SkaledPorts  # noqa

SChainRule = namedtuple(
    'SChainRule',
    ['port', 'first_ip', 'last_ip'],
    defaults=(None, None,)
)
