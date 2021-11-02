import importlib
import logging
import threading
import multiprocessing
from collections import namedtuple
from typing import Dict, Generator, Optional

from core.schains.firewall import IFirewallManager, SChainRule

logger = logging.getLogger(__name__)

try:
    import iptc
except (FileNotFoundError, AttributeError):
    logger.warning('Unable to import iptc')


TABLE = 'filter'
CHAIN = 'INPUT'
BASE_RULE_D = {
    'protocol': 'tcp',
    'target': 'ACCEPT'
}


lock = threading.Lock()
plock = multiprocessing.Lock()


class IptablesManager(IFirewallManager):
    def __init__(self, table: str = TABLE, chain: str = CHAIN):
        self.table = table
        self.chain = chain
        self.iptc = importlib.import_module('iptc')

    def add_rule(self, rule: SChainRule) -> None:
        if not self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                iptc.easy.insert_rule(self.table, self.chain, rule_d)

    def remove_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                iptc.easy.delete_rule(self.table, self.chain, rule_d)

    @classmethod
    def is_manageable(cls, rule_d: Dict) -> bool:
        # TODO: Think about comments
        return all((
            rule_d.get('protocol') == 'tcp',
            rule_d.get('target') == 'ACCEPT',
            rule_d.get('tcp', {}).get('dport') is not None
        ))

    @property
    def rules(self) -> Generator[SChainRule, SChainRule, SChainRule]:
        ichain = iptc.Chain(iptc.Table(self.table), self.chain)
        for irule in ichain.rules:
            rule_d = iptc.easy.decode_iptc_rule(irule)
            if self.is_manageable(rule_d):
                yield self.rule_d_to_schain_rule(rule_d)

    def has_rule(self, rule: SChainRule) -> bool:
        rule_d = self.schain_rule_to_rule_d(rule)
        return self.iptc.easy.has_rule(self.table, self.chain, rule_d)

    def schain_rule_to_rule_d(self, srule: SChainRule) -> Dict:
        rule = {
            'protocol': 'tcp',
            'tcp': {'dport': str(srule.port)},
            'target': 'ACCEPT'
        }
        if srule.first_ip is not None:
            if srule.first_ip == srule.last_ip or srule.last_ip is None:
                rule.update({'src': srule.first_ip})
            else:
                rule.update({
                    'iprange': {
                        'src-range': f'{srule.first_ip}-{srule.last_ip}'
                    }
                })
        return rule

    def rule_d_to_schain_rule(self, rule_d: Dict) -> SChainRule:
        first_ip, last_ip = None, None
        iprange = rule_d.get('iprange')
        src = rule_d.get('src')
        if iprange:
            first_ip, last_ip = iprange['src-range'].split('-')
        elif src:
            first_ip = last_ip = rule_d['src']
        port = int(rule_d['tcp']['dport'])

        return SChainRule(port, first_ip, last_ip)


def compose_rule(
    port: int,
    start_ip: str,
    end_ip: str,
    target: str = 'ACCEPT',
    comment: Optional[str] = None
) -> None:
    # {'protocol': 'tcp', 'tcp': {'dport': '1000'}, 'iprange': {'src-range':
    # '1.1.1.1-2.2.2.2'}, 'target': 'ACCEPT'}
    rule = iptc.Rule()
    rule.protocol = 'tcp'

    port_match = iptc.Match(rule, 'tcp')
    port_match.dport = str(port)
    rule.add_match(port_match)

    src_match = None
    if start_ip == end_ip:
        src_match = iptc.Match(rule, 'src')
        src_match.src_range = start_ip
    else:
        src_match = iptc.Match(rule, 'iprange')
        src_match.src_range = f'{start_ip}-{end_ip}'
    rule.add_match(src_match)

    rule.target = iptc.Target(rule, target)
    return rule


def add_rule(rule: iptc.Rule, chain: str = 'INPUT') -> None:
    ichain = iptc.Chain(iptc.Table(iptc.Table.FILTER), chain)
    with lock:
        ichain.insert_rule(rule)


def delete_rule(rule: iptc.Rule, chain: str = 'INPUT') -> None:
    ichain = iptc.Chain(iptc.Table(iptc.Table.FILTER), chain)
    with lock:
        ichain.delete_rule(rule)


def has_rule(rule: iptc.Rule, chain: str = 'INPUT') -> None:
    ichain = iptc.Chain(iptc.Table(iptc.Table.FILTER), chain)
    return ichain.has_rule(rule)


NodeEndpoint = namedtuple('NodeEndpoint', ['ip', 'port'])


def rule_d_from_endpoint(endpoint):
    rule_d = BASE_RULE_D.copy()
    if endpoint.ip is not None:
        rule_d['src'] = str(endpoint.ip)
    if endpoint.port is not None:
        rule_d['tcp'] = {'dport': str(endpoint.port)}
    return rule_d


def apsent_rules(endpoints):
    apsent = []
    for endpoint in endpoints:
        rule_d = rule_d_from_endpoint(endpoint)
        with lock:
            if not iptc.easy.has_rule(TABLE, CHAIN, rule_d):
                apsent.append((endpoint.ip, endpoint.port))
    return apsent


def add_rules(endpoints):
    logger.info(f'Such endpoints will be added to iptables rules {endpoints}')
    for endpoint in endpoints:
        rule_d = rule_d_from_endpoint(endpoint)
        with lock:
            if not iptc.easy.has_rule(TABLE, CHAIN, rule_d):
                iptc.easy.insert_rule(TABLE, CHAIN, rule_d)
            else:
                logger.warning(f'Rule {rule_d} is already in iptables rules')
    logger.info('Endpoints successfully added')


def remove_rules(endpoints):
    logger.info(
        f'Such endpoints would be removed from iptables rules {endpoints}')
    for endpoint in endpoints:
        rule_d = rule_d_from_endpoint(endpoint)
        with lock:
            if iptc.easy.has_rule(TABLE, CHAIN, rule_d):
                iptc.easy.delete_rule(TABLE, CHAIN, rule_d)
            else:
                logger.warning(
                    f'Rule {rule_d} hasn\'t beed added to iptables rules')
    logger.info('Endpoints successfully removed')
