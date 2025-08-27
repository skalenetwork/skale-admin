#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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
from http import HTTPStatus
from typing import Iterable

from flask import Blueprint, Response, g, request
from skale.transactions.exceptions import TransactionError
from skale.utils.web3_utils import to_checksum_address

from core.node_config import NodeConfig
from web.helper import (
    construct_err_response,
    construct_key_error_response,
    construct_ok_response,
    g_fair,
    get_api_url,
)

logger = logging.getLogger(__name__)

BLUEPRINT_NAME = 'fair-staking'
fair_staking_bp = Blueprint(BLUEPRINT_NAME, __name__)


def _get_body(required: Iterable[str] | None = None) -> tuple[dict, Response | None]:
    body = request.get_json(silent=True) or {}
    if required:
        absent = [k for k in required if k not in body]
        if absent:
            return {}, construct_key_error_response(absent)
    return body, None


def _node_id_or_error(node_config: NodeConfig) -> tuple[int | None, Response | None]:
    if not node_config.id:
        return None, construct_err_response(
            msg='Node is not registered', status_code=HTTPStatus.BAD_REQUEST
        )
    return node_config.id, None


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'add-receiver'), methods=['POST'])
@g_fair
def add_receiver() -> Response:
    body, err = _get_body(['receiver'])
    if err:
        return err
    try:
        receiver = to_checksum_address(str(body['receiver']))
    except Exception as e:
        logger.exception('Invalid receiver address: %s', e)
        return construct_err_response('Invalid receiver address')
    try:
        g.fair.staking.add_allowed_receiver(receiver)
    except TransactionError as e:
        logger.error('Error addAllowedReceiver: %s', e)
        return construct_err_response(
            msg=f'Error addAllowedReceiver: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'remove-receiver'), methods=['POST'])
@g_fair
def remove_receiver() -> Response:
    body, err = _get_body(['receiver'])
    if err:
        return err
    try:
        receiver = to_checksum_address(str(body['receiver']))
    except Exception:
        return construct_err_response('Invalid receiver address')
    try:
        g.fair.staking.remove_allowed_receiver(receiver)
    except TransactionError as e:
        logger.error('Error removeAllowedReceiver: %s', e)
        return construct_err_response(
            msg=f'Error removeAllowedReceiver: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'set-fee-rate'), methods=['POST'])
@g_fair
def set_fee_rate() -> Response:
    body, err = _get_body(['feeRate'])
    if err:
        return err
    try:
        fee_rate = int(body['feeRate'])
    except Exception:
        return construct_err_response('Invalid feeRate')
    try:
        g.fair.staking.set_fee_rate(fee_rate)
    except TransactionError as e:
        logger.error('Error setFeeRate: %s', e)
        return construct_err_response(
            msg=f'Error setFeeRate: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'claim-fees'), methods=['POST'])
@g_fair
def claim_fees() -> Response:
    body, err = _get_body()
    if err:
        return err
    node_config: NodeConfig = g.config
    node_id, node_err = _node_id_or_error(node_config)
    if node_err:
        return node_err
    amount = body.get('amount')
    try:
        if amount is None or amount == '':
            g.fair.staking.claim_all_fees(node_id)
        else:
            amount_wei = g.fair.web3.to_wei(amount, 'ether')
            g.fair.staking.claim_fees(node_id, int(amount_wei))
    except TransactionError as e:
        logger.error('Error claimFees: %s', e)
        return construct_err_response(
            msg=f'Error claimFees: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'send-fees'), methods=['POST'])
@g_fair
def send_fees() -> Response:
    body, err = _get_body(['to'])
    if err:
        return err
    try:
        to = to_checksum_address(str(body['to']))
    except Exception:
        return construct_err_response('Invalid recipient address')
    amount = body.get('amount')

    try:
        if amount is None or amount == '':
            g.fair.staking.send_all_fees(to)
        else:
            amount_wei = g.fair.web3.to_wei(amount, 'ether')
            g.fair.staking.send_fees(to, int(amount_wei))
    except TransactionError as e:
        logger.error('Error sendFees: %s', e)
        return construct_err_response(
            msg=f'Error sendFees: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response()


@fair_staking_bp.route(get_api_url(BLUEPRINT_NAME, 'get-earned-fee-amount'), methods=['POST'])
@g_fair
def get_earned_fee_amount() -> Response:
    node_config: NodeConfig = g.config
    node_id, err = _node_id_or_error(node_config)
    if err:
        return err
    try:
        amount_wei = g.fair.staking.get_earned_fee_amount(node_id)
    except Exception as e:
        logger.error('Error getEarnedFeeAmount: %s', e)
        return construct_err_response(
            msg=f'Error getEarnedFeeAmount: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return construct_ok_response(
        {
            'amount_wei': int(amount_wei),
            'amount_ether': str(g.fair.web3.from_wei(int(amount_wei), 'ether')),
        }
    )
