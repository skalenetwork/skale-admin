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

from web3.exceptions import TransactionNotFound

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
        self.event_hash = "0x47e57a213b52c1c14550e5456a6dcdbf44bb6e87c0832fdde78d996977e6904d"
        self.n = n
        self.t = (2 * n + 1) // 3
        # TODO: use scheme below to calculate event hash
        # self.skale.web3.to_hex(self.skale.web3.keccak(
        #                             text="BroadcastAndKeyShare(bytes32,uint256,tuple[],tuple[])")
        #                 )

    def check_event(self, receipt):
        logs = receipt.get('logs')
        if not logs:
            logger.info(f'sChain {self.group_index_str}: receipt {receipt}'
                        f' does not have field "logs"')
            return False
        if len(logs) == 0:
            return False
        topics = logs[0].get('topics')
        if not topics:
            logger.info(f'sChain {self.group_index_str}: receipt {receipt}'
                        f' does not have field "topics"')
            return False
        if len(topics) < 2:
            return False
        if topics[0].hex() != self.event_hash:
            return False
        if topics[1].hex() != self.group_index_str:
            return False
        data = logs[0].get('data')
        if not data:
            logger.info(f'sChain {self.group_index_str}: receipt {receipt}'
                        f' does not have field "data"')
            return False
        return True

    def parse_event(self, receipt):
        event_data = receipt['logs'][0]['data'].hex()[2:]
        node_index = int(receipt['logs'][0]['topics'][2].hex()[2:], 16)
        vv = event_data[192: 192 + self.t * 256]
        skc = event_data[192 + 64 + self.t * 256: 192 + 64 + self.t * 256 + 192 * self.n]
        return DKGEvent(**{
            'nodeIndex': node_index, "secretKeyContribution": skc, "verificationVector": vv
            })

    def get_events(self, from_channel_started_block=False):
        try:
            if self.first_unseen_block == -1 or from_channel_started_block:
                start_block = self.dkg_contract.functions.getChannelStartedBlock(
                    self.group_index
                ).call()
            else:
                start_block = self.first_unseen_block
            current_block = self.skale.web3.eth.get_block("latest")["number"]
            logger.info(f'sChain {self.group_index_str}: Parsing broadcast events '
                        f'from {start_block} block to {current_block} block')
            events = []
            for block_number in range(start_block, current_block + 1):
                block = self.skale.web3.eth.get_block(block_number, full_transactions=True)
                txns = block["transactions"]
                for tx in txns:
                    try:
                        if tx.get("to") != self.dkg_contract_address:
                            continue

                        hash = tx.get("hash")
                        if hash:
                            receipt = self.skale.web3.eth.get_transaction_receipt(hash)
                        else:
                            logger.info(f'sChain {self.group_index_str}: tx {tx}'
                                        f' does not have field "hash"')
                            continue

                        if not self.check_event(receipt):
                            continue
                        else:
                            events.append(self.parse_event(receipt))
                    except TransactionNotFound:
                        pass
                self.first_unseen_block = block_number + 1
            return events
        except Exception as e:
            logger.info(f'sChain {self.group_index_str}: error during collecting broadcast '
                        f'events: {e}')
            return []
