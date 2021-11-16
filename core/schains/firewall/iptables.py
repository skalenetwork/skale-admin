#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.


import logging
import importlib
import ipaddress
import multiprocessing
from functools import wraps
from typing import Callable, Dict, Iterable

from core.schains.firewall.types import IHostFirewallManager, SChainRule

logger = logging.getLogger(__name__)

TABLE = 'filter'
CHAIN = 'INPUT'

plock = multiprocessing.Lock()


def refreshed(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.refresh()
        return func(self, *args, **kwargs)
    return wrapper


class IptablesManager(IHostFirewallManager):
    def __init__(self, table: str = TABLE, chain: str = CHAIN):
        self.table = table
        self.chain = chain
        self.iptc = importlib.import_module('iptc')
        self.iptc = importlib.reload(self.iptc)

    def refresh(self):
        self.iptc.Table(self.table).refresh()

    @refreshed
    def add_rule(self, rule: SChainRule) -> None:
        if not self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                self.iptc.easy.insert_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

    @refreshed
    def remove_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            rule_d = self.schain_rule_to_rule_d(rule)
            with plock:
                self.iptc.easy.delete_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

    @classmethod
    def is_manageable(cls, rule_d: Dict) -> bool:
        return all((
            rule_d.get('protocol') == 'tcp',
            rule_d.get('target') == 'ACCEPT',
            rule_d.get('tcp', {}).get('dport') is not None
        ))

    @property
    @refreshed
    def rules(self) -> Iterable[SChainRule]:
        ichain = self.iptc.Chain(self.iptc.Table(self.table), self.chain)  # type: ignore  # noqa
        for irule in ichain.rules:
            rule_d = self.iptc.easy.decode_iptc_rule(irule)  # type: ignore  # noqa
            if self.is_manageable(rule_d):
                yield self.rule_d_to_schain_rule(rule_d)

    @refreshed
    def has_rule(self, rule: SChainRule) -> bool:
        rule_d = self.schain_rule_to_rule_d(rule)
        return self.iptc.easy.has_rule(self.table, self.chain, rule_d)  # type: ignore  # noqa

    @classmethod
    def schain_rule_to_rule_d(cls, srule: SChainRule) -> Dict:
        rule = {
            'protocol': 'tcp',
            'tcp': {'dport': str(srule.port)},
            'target': 'ACCEPT'
        }
        if srule.first_ip is not None:
            if srule.first_ip == srule.last_ip or srule.last_ip is None:
                rule.update({'src': cls.to_ip_network(srule.first_ip)})
            else:
                rule.update({
                    'iprange': {
                        'src-range': f'{srule.first_ip}-{srule.last_ip}'
                    }
                })
        return rule

    @classmethod
    def rule_d_to_schain_rule(cls, rule_d: Dict) -> SChainRule:
        first_ip, last_ip = None, None
        iprange = rule_d.get('iprange')
        src = rule_d.get('src')
        if iprange:
            first_ip, last_ip = iprange['src-range'].split('-')
        elif src:
            first_ip = rule_d['src']
            first_ip = cls.from_ip_network(rule_d['src'])
        port = int(rule_d['tcp']['dport'])

        return SChainRule(port, first_ip, last_ip)

    @classmethod
    def from_ip_network(cls, ip: str) -> str:
        return str(ipaddress.ip_network(ip).hosts()[0])

    @classmethod
    def to_ip_network(cls, ip: str) -> str:
        return str(ipaddress.ip_network(ip))
