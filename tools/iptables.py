import logging
import threading

from collections import namedtuple

logger = logging.getLogger(__name__)

try:
    import iptc
except FileNotFoundError:
    logger.warning('Unable to import iptc')


TABLE = 'filter'
CHAIN = 'INPUT'
BASE_RULE_D = {
    'protocol': 'tcp',
    'target': 'ACCEPT'
}


lock = threading.Lock()

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
    logger.info(f'Such endpoints would be removed from iptables rules {endpoints}')
    for endpoint in endpoints:
        rule_d = rule_d_from_endpoint(endpoint)
        with lock:
            if iptc.easy.has_rule(TABLE, CHAIN, rule_d):
                iptc.easy.delete_rule(TABLE, CHAIN, rule_d)
            else:
                logger.warning(f'Rule {rule_d} hasn\'t beed added to iptables rules')
    logger.info('Endpoints successfully removed')
