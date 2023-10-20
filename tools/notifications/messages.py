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
import time
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional

from redis import BlockingConnectionPool, Redis

from tools.configs.tg import CHECKS_STATE_EXPIRATION, TG_API_KEY, TG_CHAT_ID
from tools.notifications.tasks import send_message_to_telegram


logger = logging.getLogger(__name__)
redis_client = Redis(connection_pool=BlockingConnectionPool())


RED_LIGHT = '\u274C'
GREEN_LIGHT = '\u2705'
EXCLAMATION_MARK = '\u2757'
SUCCESS_MAX_ATTEMPS = 1
FAILED_MAX_ATTEMPS = 1


def tg_notifications_enabled() -> bool:
    return TG_API_KEY and TG_CHAT_ID


def notifications_enabled(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if tg_notifications_enabled():
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.exception(
                    'Notification %s sending failed', func.__name__)

    return wrapper


@notifications_enabled
def cleanup_notification_state(*, client: Optional[Redis] = None) -> None:
    client = client or redis_client
    keys = client.keys('messages.*')
    logger.info(f'Removing following keys from notificaton state: {keys}')
    if keys:
        client.delete(*keys)


def is_checks_passed(checks: Dict) -> bool:
    return all(checks.values())


def compose_checks_message(
    schain_name: str,
    node: Dict,
    checks: Dict,
    raw: bool = False
):
    if raw:
        msg = {
            'schain_name': schain_name,
            'node_id': node['node_id'],
            'node_ip': node['node_ip'],
            'checks': checks,
        }
    else:
        msg = [
            f'Node ID: {node["node_id"]}, IP: {node["node_ip"]}',
            f'sChain name: {schain_name}'
        ]
        if is_checks_passed(checks):
            msg.append(f'\n{GREEN_LIGHT} All checks passed')
            return msg
        msg.append(f'\n{EXCLAMATION_MARK} Some checks failed\n')
        for check in checks:
            if not checks[check]:
                msg.append(f'{RED_LIGHT} {check}')
    return msg


def get_state_from_checks(checks: Dict) -> str:
    return str(sorted(checks.items()))


@notifications_enabled
def notify_checks(
    schain_name: str,
    node: Dict,
    checks: Dict,
    *,
    client: Optional[Redis] = None
) -> None:
    client = client or redis_client
    count_key = f'messages.checks.{schain_name}.count'
    state_key = f'messages.checks.{schain_name}.state'
    saved_state_bytes = client.get(state_key) or b''
    saved_state = saved_state_bytes.decode('utf-8')
    count = 0
    if saved_state:
        count = int(client.get(count_key) or 0)
    state = get_state_from_checks(checks)

    success = is_checks_passed(checks)

    if saved_state != state or (
        success and count < SUCCESS_MAX_ATTEMPS or
            not success and count < FAILED_MAX_ATTEMPS):
        message = compose_checks_message(schain_name, node, checks)
        logger.info(f'Sending checks notification with state {state}')
        send_message(message)

    if saved_state != state:
        count = 1
        logger.info(f'Saving new checks state {count} {state}')
        ex = None if success else CHECKS_STATE_EXPIRATION
        pipe = client.pipeline()
        pipe.set(state_key, state, ex=ex)
        pipe.set(count_key, count)
        pipe.execute()
    else:
        count += 1
        logger.info(f'Saving new checks count {count}')
        client.set(count_key, count)


def compose_balance_message(
    node_info: Dict,
    balance: float,
    required_balance: float
) -> List[str]:
    if balance < required_balance:
        header = f'{EXCLAMATION_MARK} Balance on node is too low \n'
    else:
        header = f'{GREEN_LIGHT} Node id: has enough balance \n'
    return [
        header,
        f'Node ID: {node_info["node_id"]}, IP: {node_info["node_ip"]}',
        f'Balance: {balance} ETH',
        f'Required: {required_balance} ETH'
    ]


@notifications_enabled
def notify_balance(
    node_info: Dict,
    balance: float,
    required_balance: float,
    *,
    client: Optional[Redis] = None
) -> None:
    client = client or redis_client
    count_key = 'messages.balance.count'
    state_key = 'messages.balance.state'
    count = int(client.get(count_key) or 0)
    saved_state = int(client.get(state_key) or -1)
    state = int(balance > required_balance)
    success = balance > required_balance

    if saved_state != state or (
        success and count < SUCCESS_MAX_ATTEMPS or
        not success and count < FAILED_MAX_ATTEMPS
    ):
        message = compose_balance_message(node_info, balance, required_balance)
        logger.info(f'Sending balance notificaton {state}')
        send_message(message)

    count = 1 if saved_state != state else count + 1
    logger.info(f'Saving new balance state {count} {state}')
    client.mset({count_key: count, state_key: str(state)})


def compose_repair_mode_notification(
    node_info: Dict,
    schain_name: str
) -> List:
    header = f'{EXCLAMATION_MARK} Repair mode for {schain_name} enabled \n'
    return [
        header,
        f'Node ID: {node_info["node_id"]}',
        f'Node IP: {node_info["node_ip"]}',
        f'SChain: {schain_name}'
    ]


@notifications_enabled
def notify_repair_mode(node_info: Dict, schain_name: str) -> None:
    message = compose_repair_mode_notification(node_info, schain_name)
    logger.info('Sending repair mode notification')
    send_message(message)


def send_message(message: List, api_key: str = TG_API_KEY,
                 chat_id: str = TG_CHAT_ID):
    message.extend([
        f'\nTimestamp: {int(time.time())}',
        f'Datetime: {datetime.utcnow().ctime()}'
    ])
    plain_message = '\n'.join(message)
    return send_message_to_telegram.delay(api_key, chat_id, plain_message)
