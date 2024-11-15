#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2024 SKALE Labs
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
from typing import Callable, Iterable

from core.schains.firewall.types import IHostFirewallController, SChainRule

from typing import TypeVar
import json

T = TypeVar('T')


logger = logging.getLogger(__name__)

TABLE = 'filter'
CHAIN = 'INPUT'


def refreshed(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.refresh()
        return func(self, *args, **kwargs)

    return wrapper


def is_like_number(value):
    if value is None:
        return False
    try:
        int(value)
    except ValueError:
        return False
    return True


class NftablesCmdFailedError(Exception):
    pass


class NftablesController(IHostFirewallController):
    plock = multiprocessing.Lock()
    FAMILY = 'inet'

    def __init__(self, table: str = TABLE, chain: str = CHAIN) -> None:
        self.table = table
        self.chain = chain
        self._nftables = importlib.import_module('nftables')
        self.nft = self._nftables.Nftables()
        self.nft.set_json_output(True)

    def _compose_json(self, commands: list[dict]) -> dict:
        json_cmd = {'nftables': commands}
        self.nft.json_validate(json_cmd)
        return json_cmd

    def create_table(self) -> None:
        if not self.has_table(self.table):
            return self.run_cmd(f'add table inet {self.table}')

    def create_chain(self) -> None:
        if not self.has_chain(self.chain):
            return self.run_json_cmd(
                self._compose_json(
                    [
                        {
                            'add': {
                                'chain': {
                                    'family': self.FAMILY,
                                    'table': self.table,
                                    'name': self.chain,
                                    'hook': 'input',
                                }
                            }
                        }
                    ]
                )
            )

    @property
    def chains(self) -> list[dict]:
        output = self.run_cmd('list chains')
        if output[0] != 0:
            raise NftablesCmdFailedError(output)
        parsed = json.loads(output[1])['nftables']
        return [record['chain']['name'] for record in parsed if 'chain' in record]

    @property
    def tables(self) -> list[dict]:
        output = self.run_cmd('list tables')
        if output[0] != 0:
            raise NftablesCmdFailedError(output)
        parsed = json.loads(output[1])['nftables']
        return [record['table']['name'] for record in parsed if 'table' in record]

    def run_json_cmd(self, cmd: dict) -> tuple:
        logger.debug('Nftables json cmd %s', cmd)
        with self.plock:
            return self.nft.json_cmd(cmd)

    def run_cmd(self, cmd: str) -> tuple:
        logger.debug('Nftables cmd %s', cmd)
        with self.plock:
            return self.nft.cmd(cmd)

    def has_chain(self, chain: str) -> bool:
        return chain in self.chains

    def has_table(self, table: str) -> bool:
        return table in self.tables

    def add_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            return
        expr = self.rule_to_expr(rule)

        json_cmd = self._compose_json(
            [
                {
                    'add': {
                        'rule': {
                            'family': self.FAMILY,
                            'table': self.table,
                            'chain': self.chain,
                            'expr': expr,
                        }
                    }
                }
            ]
        )

        rc, output, error = self.run_json_cmd(json_cmd)
        if rc != 0:
            raise NftablesCmdFailedError(f'Failed to add allow rule: {error}')

    @classmethod
    def rule_to_expr(cls, rule: SChainRule) -> list:
        expr = []

        if rule.first_ip:
            if rule.last_ip == rule.first_ip:
                expr.append(
                    {
                        'match': {
                            'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}},
                            'op': '==',
                            'right': f'{rule.first_ip}',
                        }
                    }
                )
            else:
                expr.append(
                    {
                        'match': {
                            'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}},
                            'op': '==',
                            'right': {'range': [f'{rule.first_ip}', f'{rule.last_ip}']},
                        }
                    }
                )

        if rule.port:
            expr.append(
                {
                    'match': {
                        'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                        'op': '==',
                        'right': rule.port,
                    }
                }
            )

        expr.append({'accept': None})
        return expr

    @classmethod
    def expr_to_rule(self, expr: list) -> None:
        port, first_ip, last_ip = None, None, None
        for item in expr:
            if 'match' in item:
                match = item['match']

                if match.get('left', {}).get('payload', {}).get('field') == 'dport':
                    port = match.get('right')

                if match.get('left', {}).get('payload', {}).get('field') == 'saddr':
                    right = match.get('right')
                    if isinstance(right, str):
                        first_ip = right
                    else:
                        first_ip, last_ip = right['range']

        if any([port, first_ip, last_ip]):
            return SChainRule(port=port, first_ip=first_ip, last_ip=last_ip)

    def remove_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            expr = self.rule_to_expr(rule)

            output = None
            rc, output, error = self.run_cmd(f'list chain {self.FAMILY} {self.table} {self.chain}')
            if rc != 0:
                raise Exception(f'Failed to list rules: {error}')

            current_rules = json.loads(output)

            handle = None
            for item in current_rules.get('nftables', []):
                if 'rule' in item:
                    rule_data = item['rule']
                    if rule_data.get('expr') == expr:
                        handle = rule_data.get('handle')
                        break

            if handle is None:
                raise Exception('Rule not found')

            json_cmd = self._compose_json(
                [
                    {
                        'delete': {
                            'rule': {
                                'family': self.FAMILY,
                                'table': self.table,
                                'chain': self.chain,
                                'handle': handle,
                            }
                        }
                    }
                ]
            )

            rc, output, error = self.run_json_cmd(json_cmd)
            if rc != 0:
                raise NftablesCmdFailedError(f'Failed to delete rule: {error}')

    @property  # type: ignore
    def rules(self) -> Iterable[SChainRule]:
        output = None
        rc, output, error = self.run_cmd(f'list chain {self.FAMILY} {self.table} {self.chain}')
        if output == '':
            return []

        data = json.loads(output)
        rules = []

        for item in data.get('nftables', []):
            if 'rule' in item:
                plain_rule = item['rule']
                rule = self.expr_to_rule(plain_rule.get('expr', []))
                if rule:
                    rules.append(rule)
        return rules

    def has_rule(self, rule: SChainRule) -> bool:
        return rule in self.rules

    @classmethod
    def from_ip_network(cls, ip: str) -> str:
        return str(ipaddress.ip_network(ip).hosts()[0])

    @classmethod
    def to_ip_network(cls, ip: str) -> str:
        return str(ipaddress.ip_network(ip))
