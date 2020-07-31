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


class Filter:
    def __init__(self, skale, schain_name):
        self.skale = skale
        self.schain_name = schain_name
        self.group_index = skale.web3.sha3(text=self.schain_name)
        self.last_viewed_block = -1
        self.dkg_contract = skale.dkg.contract.functions
        self.events = []

    def get_events(self):
        start_block = -1
        if self.last_viewed_block == -1:
            start_block = self.dkg_contract.functions.getChannelStartedBlock(
                self.group_index
            ).call({'from': self.skale.wallet.address})
        current_block = self.skale.web3.eth.getBlock()["blockNumber"]
        self.events.clear()
        for block_number in range(max(start_block, self.last_viewed_block), current_block + 1):
            block = self.skale.web3.eth.getBlock(block_number)
            txns = block["transactions"]
            for tx in txns:
                receipt = self.skale.web3.eth.getTransactionReceipt(tx)
                self.events = [event["args"] for event in receipt["logs"] if event["event"] == "BroadcastAndKeyShare" and event["args"]["groupIndex"] == self.group_index]
            self.last_viewed_block = current_block + 1
        return self.events
