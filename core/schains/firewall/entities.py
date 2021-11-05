from collections import namedtuple
from skale.dataclasses.skaled_ports import SkaledPorts  # noqa
from skale.schain_config import PORTS_PER_SCHAIN  # noqa

SChainRule = namedtuple(
    'SChainRule',
    ['port', 'first_ip', 'last_ip'],
    defaults=(None, None,)
)

IpRange = namedtuple('IpRange', ['start_ip', 'end_ip'])
