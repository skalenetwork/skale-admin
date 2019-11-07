#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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
from datetime import datetime

from flask import Blueprint, request

from core.db import BountyEvent
from core.node.utils import get_node_id
from web.helper import construct_ok_response, login_required

logger = logging.getLogger(__name__)

BLOCK_STEP = 1000
FILTER_PERIOD = 12


def construct_metrics_bp(skale, config):
    metrics_bp = Blueprint('metrics', __name__)

    def get_start_date():
        node_id = get_node_id(config)
        return skale.nodes_data.get(node_id)['start_date']

    def get_last_reward_date():
        node_id = get_node_id(config)
        return skale.nodes_data.get(node_id)['last_reward_date']

    def find_block_for_tx_stamp(tx_stamp, lo=0, hi=None):
        if hi is None:
            hi = skale.web3.eth.blockNumber
        while lo < hi:
            mid = (lo + hi) // 2
            block_data = skale.web3.eth.getBlock(mid)
            midval = datetime.utcfromtimestamp(block_data['timestamp'])
            if midval < tx_stamp:
                lo = mid + 1
            elif midval > tx_stamp:
                hi = mid
            else:
                return mid
        return lo - 1

    def get_bounty_from_db(is_from_begin=True, limit=None):
        if limit is None:
            bounties = BountyEvent.select(BountyEvent.tx_dt, BountyEvent.bounty,
                                          BountyEvent.downtime,
                                          BountyEvent.latency)
        else:
            if is_from_begin:
                bounties = BountyEvent.select(BountyEvent.tx_dt, BountyEvent.bounty,
                                              BountyEvent.downtime,
                                              BountyEvent.latency).limit(limit)
            else:
                bounties = BountyEvent.select(BountyEvent.tx_dt, BountyEvent.bounty,
                                              BountyEvent.downtime,
                                              BountyEvent.latency).order_by(
                    BountyEvent.tx_dt.desc()).limit(
                    limit)

        bounties_list = []
        for bounty in bounties:
            bounties_list.append(
                [str(bounty.tx_dt), bounty.bounty, bounty.downtime, bounty.latency])
        return bounties_list

    def get_bounty_from_events(start_date, end_date=None, is_limited=True):
        node_id = get_node_id(config)
        bounties = []
        start_block_number = find_block_for_tx_stamp(start_date)
        cur_block_number = skale.web3.eth.blockNumber
        last_block_number = find_block_for_tx_stamp(end_date) if end_date is not None \
            else cur_block_number
        while True and len(bounties) < FILTER_PERIOD:
            end_chunk_block_number = start_block_number + BLOCK_STEP - 1
            if end_chunk_block_number > last_block_number:
                end_chunk_block_number = last_block_number

            event_filter = skale.manager.contract.events.BountyGot().createFilter(
                argument_filters={'nodeIndex': node_id},
                fromBlock=hex(start_block_number),
                toBlock=hex(end_chunk_block_number))
            logs = event_filter.get_all_entries()

            for log in logs:
                args = log['args']

                tx_block_number = log['blockNumber']
                block_data = skale.web3.eth.getBlock(tx_block_number)
                block_timestamp = str(datetime.utcfromtimestamp(block_data['timestamp']))
                bounties.append([
                    block_timestamp,
                    args['bounty'],
                    args['averageDowntime'],
                    int(args['averageLatency'] / 1000)
                ])
                if is_limited and len(bounties) >= FILTER_PERIOD:
                    break
            start_block_number = start_block_number + BLOCK_STEP
            if end_chunk_block_number >= last_block_number:
                break
        return bounties

    @metrics_bp.route('/last-bounty', methods=['GET'])
    @login_required
    def bounty():
        last_reward_date = datetime.utcfromtimestamp(get_last_reward_date())
        bounties_list = get_bounty_from_events(last_reward_date)
        return construct_ok_response({'bounties': bounties_list})

    @metrics_bp.route('/first-bounties', methods=['GET'])
    @login_required
    def first_bounties():
        force = request.args.get('force') == 'True'
        if force:
            node_start_date = datetime.utcfromtimestamp(get_start_date())
            bounties_list = get_bounty_from_events(node_start_date)
        else:
            bounties_list = get_bounty_from_db(True, 12)
        return construct_ok_response({'bounties': bounties_list})

    @metrics_bp.route('/last-bounties', methods=['GET'])
    @login_required
    def last_bounties():
        force = request.args.get('force') == 'True'
        if force:
            node_start_date = get_start_date()
            last_reward_date = get_last_reward_date()
            reward_period = skale.validators_data.get_reward_period()
            start_date = datetime.utcfromtimestamp(max(last_reward_date - (
                    reward_period * (FILTER_PERIOD + 1)), node_start_date))
            bounties_list = get_bounty_from_events(start_date)
        else:
            bounties_list = get_bounty_from_db(False, 12)
        return construct_ok_response({'bounties': bounties_list})

    @metrics_bp.route('/all-bounties', methods=['GET'])
    @login_required
    def all_bounties():
        force = request.args.get('force') == 'True'
        if force:
            node_start_date = datetime.utcfromtimestamp(get_start_date())
            bounties_list = get_bounty_from_events(node_start_date, is_limited=False)
        else:
            bounties_list = get_bounty_from_db()

        return construct_ok_response({'bounties': bounties_list})

    return metrics_bp
