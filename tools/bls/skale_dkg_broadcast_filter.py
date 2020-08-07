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

from web3.logs import DISCARD
# from skale.contracts.dkg import G2Point, KeyShare

class Filter:
    def __init__(self, skale, schain_name, n):
        self.skale = skale
        self.group_index = skale.web3.sha3(text=schain_name)
        self.group_index_str = str(int(self.skale.web3.toHex(self.group_index)[2:], 16))
        self.last_viewed_block = -1
        self.dkg_contract = skale.dkg.contract
        self.event_hash = skale.web3.sha3(text="BroadcastAndKeyShare(bytes32,uint256,G2Operations.G2Point[],KeyStorage.KeyShare[])")
        self.n = n
        self.t = (2 * n + 1) // 3
        # print("EVENT HASH:", str(int(self.skale.web3.toHex(self.event_hash)[2:], 16)))
    
    def check_event(self, receipt):
        logs = receipt['logs']
        if len(logs) == 0:
            return False
        if logs['topics'][0] != self.event_hash:
            return False
        if logs['topics'][1] != self.group_index_str:
            return False
        return True
    
    def parse_event(self, receipt):
        event_data = receipt['logs']['data'][2:]
        node_index = int(receipt['logs']['topics'][2][2:], 16)
        # pos_vv = int(event_data[:64], 16)
        # pos_skc = int(event_data[64:128], 16)
        vv = event_data[192 : 192 + self.t * 256]
        skc = event_data[192 + 64 + self.t * 256 : 192 + 64 + self.t * 256 + 192 * self.n]
        return AttributeDict({'nodeIndex': node_index, "secretKeyContribution": skc, "verificationVector": vv})

    def get_events(self):
        # start_block = 0
        if self.last_viewed_block == -1:
            start_block = self.dkg_contract.functions.getChannelStartedBlock(
                self.group_index
            ).call({'from': self.skale.wallet.address})
        current_block = self.skale.web3.eth.getBlock("latest")["number"]
        events = []
        for block_number in range(max(start_block, self.last_viewed_block), current_block + 1):
            block = self.skale.web3.eth.getBlock(block_number)
            txns = block["transactions"]
            for tx in txns:
                receipt = self.skale.web3.eth.getTransactionReceipt(tx)
                # print(receipt)
                if self.check_event(receipt) == None:
                    continue
                else:
                    # print(self.parse_event(receipt))
                    events.append(self.parse_event(receipt))
            self.last_viewed_block = current_block + 1
        return events
