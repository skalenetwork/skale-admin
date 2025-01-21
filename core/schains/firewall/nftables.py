#   -*- coding: utf-8 -*-
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


import importlib
import json
import logging
import multiprocessing
import os
from typing import Iterable

from core.schains.firewall.types import IHostFirewallController, SChainRule

from tools.configs import NFT_CHAIN_BASE_PATH


logger = logging.getLogger(__name__)


TABLE = 'firewall'
CHAIN = 'skale'


class NFTablesCmdFailedError(Exception):
    pass


class NFTablesController(IHostFirewallController):
    plock = multiprocessing.Lock()
    FAMILY = 'inet'

    def __init__(self, table: str = TABLE, chain: str = CHAIN) -> None:
        self.table = table
        self.chain = f'skale-{chain}'
        self._nftables = importlib.import_module('nftables')
        self.nft = self._nftables.Nftables()
        self.nft.set_json_output(True)
        self.nft.set_stateless_output(True)

    @classmethod
    def rule_to_expr(cls, rule: SChainRule, counter: bool = True) -> list:
        expr = []

        if rule.first_ip:
            if rule.last_ip == rule.first_ip:
                expr.append(
                    {
                        'match': {
                            'op': '==',
                            'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}},
                            'right': f'{rule.first_ip}',
                        }
                    }
                )
            else:
                expr.append(
                    {
                        'match': {
                            'op': '==',
                            'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}},
                            'right': {'range': [f'{rule.first_ip}', f'{rule.last_ip}']},
                        }
                    }
                )

        if rule.port:
            expr.append(
                {
                    'match': {
                        'op': '==',
                        'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                        'right': rule.port,
                    }
                }
            )

        if counter:
            expr.append({'counter': None})

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

    def _compose_json(self, commands: list[dict]) -> dict:
        json_cmd = {'nftables': commands}
        self.nft.json_validate(json_cmd)
        return json_cmd

    def create_table(self) -> None:
        if not self.has_table(self.table):
            return self.run_cmd(f'add table inet {self.table}')

    def has_drop_rule(self, first_port: int, last_port: int) -> bool:
        expr = [
            {
                'match': {
                    'op': '==',
                    'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                    'right': {'range': [first_port, last_port]},
                }
            },
            {'counter': None},
            {'drop': None},
        ]

        return self.expr_to_rule(expr) in self.get_rules_by_policy(policy='drop')

    def add_schain_drop_rule(self, first_port: int, last_port: int) -> None:
        if not self.has_drop_rule(first_port, last_port):
            expr = [
                {
                    'match': {
                        'op': '==',
                        'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}},
                        'right': {'range': [first_port, last_port]},
                    }
                },
                {'counter': None},
                {'drop': None},
            ]

            cmd = {
                'nftables': [
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
            }
            self.run_json_cmd(cmd)
            logger.info('Added drop rule for chain %s', self.chain)

    def create_chain(self, first_port: int, last_port: int) -> None:
        if not self.has_chain(self.chain):
            logger.info('Creating chain %s', self.chain)
            self.run_json_cmd(
                self._compose_json(
                    [
                        {
                            'add': {
                                'chain': {
                                    'family': self.FAMILY,
                                    'table': self.table,
                                    'name': self.chain,
                                    'hook': 'input',
                                    'type': 'filter',
                                    'prio': 0,
                                    'policy': 'accept',
                                }
                            }
                        }
                    ]
                )
            )
        self.add_schain_drop_rule(first_port, last_port)
        self.save_rules()

    def delete_chain(self) -> None:
        if self.has_chain(self.chain):
            logger.info('Removing chain %s', self.chain)
            self.run_json_cmd(
                self._compose_json(
                    [
                        {
                            'delete': {
                                'chain': {
                                    'family': self.FAMILY,
                                    'table': self.table,
                                    'name': self.chain
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
            raise NFTablesCmdFailedError(output)
        parsed = json.loads(output[1])['nftables']
        return [record['chain']['name'] for record in parsed if 'chain' in record]

    @property
    def tables(self) -> list[dict]:
        output = self.run_cmd('list tables')
        if output[0] != 0:
            raise NFTablesCmdFailedError(output)
        parsed = json.loads(output[1])['nftables']
        return [record['table']['name'] for record in parsed if 'table' in record]

    def run_json_cmd(self, cmd: dict) -> tuple:
        logger.debug('NFTables json cmd %s', cmd)
        with self.plock:
            return self.nft.json_cmd(cmd)

    def run_cmd(self, cmd: str) -> tuple:
        logger.debug('NFTables cmd %s', cmd)
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
                    'insert': {
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

        rc, _, error = self.run_json_cmd(json_cmd)
        if rc != 0:
            raise NFTablesCmdFailedError(f'Failed to add allow rule: {error}')

    def remove_rule(self, rule: SChainRule) -> None:
        if self.has_rule(rule):
            expr = self.rule_to_expr(rule, counter=False)

            output = None
            rc, output, error = self.run_cmd(f'list chain {self.FAMILY} {self.table} {self.chain}')
            if rc != 0:
                raise NFTablesCmdFailedError(f'Failed to list rules: {error}')

            current_rules = json.loads(output)

            handle = None
            for item in current_rules.get('nftables', []):
                if 'rule' in item:
                    rule_data = item['rule']
                    rule_expr = list(
                        filter(lambda statement: 'counter' not in statement, rule_data['expr'])
                    )
                    if expr == rule_expr:
                        handle = rule_data.get('handle')
                        break

            if handle is None:
                raise NFTablesCmdFailedError('Rule not found')

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

            rc, _, error = self.run_json_cmd(json_cmd)
            if rc != 0:
                raise NFTablesCmdFailedError(f'Failed to delete rule: {error}')

    @property  # type: ignore
    def rules(self) -> Iterable[SChainRule]:
        return self.get_rules_by_policy(policy='accept')

    def has_rule(self, rule: SChainRule) -> bool:
        return rule in self.rules

    def get_rules_by_policy(self, policy: str) -> list[SChainRule]:
        output = None
        rc, output, error = self.run_cmd(f'list chain {self.FAMILY} {self.table} {self.chain}')
        if output == '':
            return []

        data = json.loads(output)
        rules = []

        for item in data.get('nftables', []):
            if 'rule' in item:
                plain_rule = item['rule']
                expr = plain_rule.get('expr', [])
                if {policy: None} in expr:
                    rule = self.expr_to_rule(expr)
                    if rule:
                        rules.append(rule)
        logger.debug('Rules for policy %s: %s', policy, rules)
        return rules

    def get_plain_chain_rules(self) -> str:
        self.nft.set_json_output(False)
        output = ''
        try:
            rc, output, error = self.run_cmd(
                f'list chain {self.FAMILY} {self.table} {self.chain}'
            )
            if rc != 0:
                raise NFTablesCmdFailedError(f"Failed to get table content: {error}")
        finally:
            self.nft.set_json_output(True)

        lines = output.split('\n')
        # cleanup table header
        if lines[-1] == '':
            lines = lines[1:-2]
        else:
            lines = lines[1:-1]

        # remove leading tab
        lines = list(map(lambda line: line[1:], lines))
        # Adding new line at the end to prevent validation failure
        lines.append('')
        output = '\n'.join(lines)
        return output

    @property
    def nft_chain_path(self) -> str:
        return os.path.join(NFT_CHAIN_BASE_PATH, f'{self.chain}.conf')

    def save_rules(self) -> None:
        logger.info('Saving the firewall rules for chain %s', self.chain)
        chain_rules = self.get_plain_chain_rules()
        with open(self.nft_chain_path, 'w') as nft_chain_file:
            nft_chain_file.write(chain_rules)

    def get_saved_rules(self) -> str:
        if not os.path.isfile(self.nft_chain_path):
            return ''
        with open(self.nft_chain_path, 'r') as nft_chain_file:
            return nft_chain_file.read()

    def remove_saved_rules(self) -> None:
        if os.isfile(self.nft_chain_path):
            os.remove(self.nft_chain_path)

    def cleanup(self) -> None:
        self.remove_saved_rules()
        self.delete_chain()
