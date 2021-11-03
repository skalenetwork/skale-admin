import logging
import importlib
import multiprocessing
from typing import Dict, Iterable

from core.schains.firewall.firewall_manager import IHostFirewallManager
from core.schains.firewall.entities import SChainRule

logger = logging.getLogger(__name__)

TABLE = 'filter'
CHAIN = 'INPUT'

plock = multiprocessing.Lock()


class IptablesManager(IHostFirewallManager):
    def __init__(self, table: str = TABLE, chain: str = CHAIN):
        self.table = table
        self.chain = chain
        self.iptc = importlib.import_module('iptc')

    def add_rule(self, rule: SChainRule) -> None:
        if not self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                self.iptc.easy.insert_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

    def remove_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                self.iptc.easy.delete_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

    @classmethod
    def is_manageable(cls, rule_d: Dict) -> bool:
        # IVD TODO: Think about comments
        return all((
            rule_d.get('protocol') == 'tcp',
            rule_d.get('target') == 'ACCEPT',
            rule_d.get('tcp', {}).get('dport') is not None
        ))

    @property
    def rules(self) -> Iterable[SChainRule]:
        ichain = self.iptc.Chain(self.iptc.Table(self.table), self.chain)  # type: ignore  # noqa
        for irule in ichain.rules:
            rule_d = self.iptc.easy.decode_iptc_rule(irule)  # type: ignore  # noqa
            if self.is_manageable(rule_d):
                yield self.rule_d_to_schain_rule(rule_d)

    def has_rule(self, rule: SChainRule) -> bool:
        rule_d = self.schain_rule_to_rule_d(rule)
        return self.iptc.easy.has_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

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
