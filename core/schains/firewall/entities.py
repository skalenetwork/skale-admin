from collections import namedtuple
from skale.dataclasses.skaled_ports import SkaledPorts  # noqa

SChainRule = namedtuple(
    'SChainRule',
    ['port', 'first_ip', 'last_ip'],
    defaults=(None, None,)
)
