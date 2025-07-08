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

import logging

from eth_utils.hexadecimal import remove_0x_prefix
from web3.exceptions import Web3Exception, TransactionNotFound

from core.dkg.broadcast_filter import BaseFilter, DKGEvent

logger = logging.getLogger(__name__)


class SchainFilter(BaseFilter):
    def __init__(self, skale, schain_name, n):
        self.skale = skale
        self.group_index = skale.web3.keccak(text=schain_name)
        self.group_index_str = remove_0x_prefix(self.skale.web3.to_hex(self.group_index))
        self.first_unseen_block = -1
        self.dkg_contract = skale.dkg.contract
        self.dkg_contract_address = skale.dkg.address
        self.event_hash = '47e57a213b52c1c14550e5456a6dcdbf44bb6e87c0832fdde78d996977e6904d'
        super().__init__(n)

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
            logger.info(f'sChain {self.group_index_str}: topics is less than 2')
            return False
        if topics[0].hex() != self.event_hash:
            logger.info(f'sChain {self.group_index_str}: Event hash is not equal')
            return False
        if topics[1].hex() != self.group_index_str:
            logger.info(f'sChain {self.group_index_str}: Group index is not equal')
            return False
        data = logs[0].get('data')
        if not data:
            logger.info(
                f'sChain {self.group_index_str}: receipt {receipt} does not have field "data"'
            )
            return False
        return True

    def parse_event(self, receipt):
        event_data = remove_0x_prefix(receipt['logs'][0]['data'].hex())
        node_index = int(remove_0x_prefix(receipt['logs'][0]['topics'][2].hex()), 16)
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
            current_block = self.skale.web3.eth.get_block('latest')['number']
            logger.info(
                f'sChain {self.group_index_str}: Parsing broadcast events '
                f'from {start_block} block to {current_block} block'
            )
            for block_number in range(start_block, current_block + 1):
                block = self.skale.web3.eth.get_block(block_number, full_transactions=True)
                txns = block['transactions']
                for tx in txns:
                    try:
                        if tx.get('to') != self.dkg_contract_address:
                            continue

                        hash = tx.get('hash')
                        if hash:
                            receipt = self.skale.web3.eth.get_transaction_receipt(hash)
                        else:
                            logger.info(
                                f'sChain {self.group_index_str}: tx {tx} does not have field "hash"'
                            )
                            continue

                        if not self.check_event(receipt):
                            continue
                        else:
                            events.append(self.parse_event(receipt))
                    except TransactionNotFound:
                        pass
                self.first_unseen_block = block_number + 1
            return events
        except (ValueError, Web3Exception) as e:
            logger.info(
                f'sChain {self.group_index_str}: error during collecting broadcast events: {e}'
            )
            return events
