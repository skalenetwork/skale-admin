import importlib
import logging
import threading
from collections import namedtuple
from typing import Dict, List, Optional

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


class IptablesManager:
    def __init__(self, table: str = TABLE, chain: str = CHAIN):
        self.table = table
        self.chain = chain
        self.iptc = importlib.import_module('iptc')

    def compose_rule_d(
            self,
            port: int,
            start_ip: str,
            end_ip: str,
            target: str = 'ACCEPT',
            comment: Optional[str] = None
    ) -> Dict:
        rule = {'protocol': 'tcp', 'tcp': {
            'dport': str(port)}, 'target': target}
        if start_ip == end_ip:
            rule.update({'src': start_ip})
        else:
            rule.update({'iprange': {'src-range': f'{start_ip}-{end_ip}'}})
            return rule

    def get_rules(self) -> List[Dict]:
        ichain = iptc.Chain(iptc.Table(self.table), self.chain)
        for irule in ichain.rules:
            yield iptc.easy.encode_iptc_rule(irule)

    def get_port_range_rules(self, first: int, last: int) -> List[Dict]:
        return filter(
            lambda r: first < r.get('tcp', {}).get('dport', -1) < last,
            self.get_rules
        )


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
