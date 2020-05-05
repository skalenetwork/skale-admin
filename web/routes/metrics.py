#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019-2020 SKALE Labs
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
from web3 import Web3

from core.db import get_bounty_sum, select_bounty_records_from_db
from tools.helper import SkaleFilter
from web.helper import construct_ok_response

logger = logging.getLogger(__name__)

BLOCK_CHUNK_SIZE = 1000


def construct_metrics_bp(skale, config):
    metrics_bp = Blueprint('metrics', __name__)

    def get_start_block():
        node_id = config.id
        return skale.nodes_data.get(node_id)['start_block']

    def convert_to_date(date_str):
        if date_str is None:
            return None
        else:
            format_str = '%Y-%m-%d %H:%M:%S'
            return datetime.strptime(date_str, format_str)

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

    def get_metrics_from_db(start_date=None, end_date=None, limit=None, wei=None):
        if start_date is None:
            start_date = datetime.utcfromtimestamp(0)
        if end_date is None:
            end_date = datetime.now()
        metrics = select_bounty_records_from_db(start_date, end_date, limit)

        total_bounty = int(get_bounty_sum(start_date, end_date))
        if not wei:
            total_bounty = to_skl(total_bounty)

        metrics_list = []
        for metric in metrics:
            bounty = int(metric.bounty)
            if not wei:
                bounty = to_skl(bounty)
            metrics_list.append(
                [str(metric.tx_dt), bounty, metric.downtime, metric.latency])
        return metrics_list, total_bounty

    def get_start_end_block_numbers(start_date=None, end_date=None):
        if start_date is None:
            start_block_number = get_start_block()
        else:
            start_block_number = find_block_for_tx_stamp(start_date)

        if end_date is None:
            last_block_number = skale.web3.eth.blockNumber
        else:
            last_block_number = find_block_for_tx_stamp(end_date)

        return start_block_number, last_block_number

    def to_skl(wei):  # convert to SKL
        return Web3.fromWei(wei, 'ether')

    def format_limit(limit):
        if limit is None:
            return float('inf')
        else:
            return int(limit)

    def get_metrics_from_events(start_date=None, end_date=None,
                                limit=None, wei=None):
        metrics_rows = []
        total_bounty = 0
        limit = format_limit(limit)
        start_block_number, last_block_number = get_start_end_block_numbers(
            start_date, end_date)
        start_chunk_block_number = start_block_number
        while len(metrics_rows) < limit:
            end_chunk_block_number = start_chunk_block_number + BLOCK_CHUNK_SIZE - 1
            if end_chunk_block_number > last_block_number:
                end_chunk_block_number = last_block_number

            event_filter = SkaleFilter(
                skale.manager.contract.events.BountyGot,
                from_block=hex(start_chunk_block_number),
                argument_filters={'nodeIndex': config.id},
                to_block=hex(end_chunk_block_number)
            )
            logs = event_filter.get_events()
            for log in logs:
                args = log['args']
                tx_block_number = log['blockNumber']
                block_data = skale.web3.eth.getBlock(tx_block_number)
                block_timestamp = datetime.utcfromtimestamp(
                    block_data['timestamp'])
                bounty = args['bounty']
                if not wei:
                    bounty = to_skl(bounty)
                metrics_row = [str(block_timestamp),
                               bounty,
                               args['averageDowntime'],
                               round(args['averageLatency'] / 1000, 1)]
                total_bounty += metrics_row[1]
                metrics_rows.append(metrics_row)
                if len(metrics_rows) >= limit:
                    break
            start_chunk_block_number = start_chunk_block_number + BLOCK_CHUNK_SIZE
            if end_chunk_block_number >= last_block_number:
                break
        return metrics_rows, total_bounty

    @metrics_bp.route('/metrics', methods=['GET'])
    def get_metrics():
        since = convert_to_date(request.args.get('since'))
        till = convert_to_date(request.args.get('till'))
        limit = request.args.get('limit')
        fast = request.args.get('fast') == 'True'
        wei = request.args.get('wei') == 'True'
        if fast:
            metrics, total_bounty = get_metrics_from_db(
                since, till, limit, wei)
        else:
            metrics, total_bounty = get_metrics_from_events(
                since, till, limit, wei)
        return construct_ok_response(data={'metrics': metrics, 'total': total_bounty})

    return metrics_bp
