#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2020 SKALE Labs
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

from dataclasses import dataclass
import logging
from web3.exceptions import Web3Exception

logger = logging.getLogger(__name__)


@dataclass
class DKGEvent:
    nodeIndex: str
    secretKeyContribution: str
    verificationVector: str


class Filter:
    def __init__(self, skale, schain_name, n):
        self.skale = skale
        self.group_index = skale.web3.keccak(text=schain_name)
        self.group_index_str = self.skale.web3.to_hex(self.group_index)
        self.first_unseen_block = -1
        self.dkg_contract = skale.dkg.contract
        self.dkg_contract_address = skale.dkg.address
        self.event_name = 'BroadcastAndKeyShare'
        self.n = n
        self.t = (2 * n + 1) // 3

    def check_event(self, receipt):
        logs = receipt.get('logs')
        if not logs:
            logger.info(
                f'sChain {self.group_index_str}: receipt {receipt} does not have field "logs"'
            )
            return False
        if len(logs) == 0:
            return False
        topics = logs[0].get('topics')
        if not topics:
            logger.info(
                f'sChain {self.group_index_str}: receipt {receipt} does not have field "topics"'
            )
            return False
        if len(topics) < 2:
            return False
        if topics[0].hex() != self.dkg_contract.events[self.event_name].abi['signature']:
            return False
        if topics[1].hex() != self.group_index_str:
            return False
        data = logs[0].get('data')
        if not data:
            logger.info(
                f'sChain {self.group_index_str}: receipt {receipt} does not have field "data"'
            )
            return False
        return True

    def parse_event(self, receipt):
        event_data = receipt['logs'][0]['data'].hex()[2:]
        node_index = int(receipt['logs'][0]['topics'][2].hex()[2:], 16)
        vv = event_data[192 : 192 + self.t * 256]
        skc = event_data[192 + 64 + self.t * 256 : 192 + 64 + self.t * 256 + 192 * self.n]
        return DKGEvent(
            **{'nodeIndex': node_index, 'secretKeyContribution': skc, 'verificationVector': vv}
        )

    def get_events(self, from_channel_started_block=False):
        events = []
        try:
            if self.first_unseen_block == -1 or from_channel_started_block:
                start_block = self.dkg_contract.functions.getChannelStartedBlock(
                    self.group_index
                ).call()
            else:
                start_block = self.first_unseen_block
            filter = self.dkg_contract.events[self.event_name].create_filter(fromBlock=start_block)
            raw_events = filter.get_all_entries()
            for raw_event in raw_events:
                events.append(self.parse_event(raw_event))
            if raw_events:
                self.first_unseen_block = raw_events[-1]['blockNumber'] + 1
            return events
        except (ValueError, Web3Exception) as e:
            logger.info(
                f'sChain {self.group_index_str}: error during collecting broadcast events: {e}'
            )
            return events
