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


import copy
import logging
import time
from datetime import datetime
from functools import wraps

from redis import BlockingConnectionPool, Redis

from tools.configs.tg import TG_API_KEY, TG_CHAT_ID
from tools.notifications.tasks import send_message_to_telegram


logger = logging.getLogger(__name__)
redis_client = Redis(connection_pool=BlockingConnectionPool())


RED_LIGHT = '\u274C'
GREEN_LIGHT = '\u2705'
EXCLAMATION_MARK = '\u2757'
SUCCESS_MAX_ATTEMPS = 1
FAILED_MAX_ATTEMPS = 5


def tg_notifications_enabled():
    return TG_API_KEY and TG_CHAT_ID


def notifications_enabled(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if tg_notifications_enabled():
            try:
                return func(*args, **kwargs)
            except Exception as err:
                logger.error(f'Notification {func.__name__} sending failed',
                             exc_info=err)
    return wrapper


@notifications_enabled
def cleanup_notification_state(*, client=None):
    client = client or redis_client
    keys = client.keys('messages.*')
    logger.info(f'Removing following keys from notificaton state: {keys}')
    if keys:
        client.delete(*keys)


def convert_bool_to_emoji_lights(checks):
    checks_emojis = copy.deepcopy(checks)
    for check in checks:
        checks_emojis[check] = GREEN_LIGHT if checks[check] else RED_LIGHT
    return checks_emojis


def is_checks_passed(checks):
    return all(checks.values())


def compose_checks_message(schain_name, node, checks, raw=False):
    if raw:
        message = {
            'schain_name': schain_name,
            'node_id': node['node_id'],
            'node_ip': node['node_ip'],
            'checks': checks,
        }
    else:
        formated_checks = convert_bool_to_emoji_lights(checks)

        if is_checks_passed(checks):
            header = f'{GREEN_LIGHT} Checks passed \n'
        else:
            header = f'{EXCLAMATION_MARK} Checks failed \n' \

        message = [
            header,
            f'Node id: {node["node_id"]}',
            f'Node ip: {node["node_ip"]}',
            f'sChain name: {schain_name}',
            f'Data directory: {formated_checks["data_dir"]}',
            f'DKG: {formated_checks["dkg"]}',
            f'Config: {formated_checks["config"]}',
            f'Volume: {formated_checks["volume"]}',
            f'Container: {formated_checks["container"]}',
            # f'IMA container: {formated_checks["ima_container"]}\n'
            f'Firewall: {formated_checks["firewall_rules"]}',
            f'RPC: {formated_checks["rpc"]}'
        ]
    return message


def get_state_from_checks(checks):
    return str(sorted(checks.items()))


@notifications_enabled
def notify_checks(schain_name, node, checks, *, client=None):
    client = client or redis_client
    count_key = 'messages.checks.count'
    state_key = 'messages.checks.state'
    count = int(client.get(count_key) or 0)
    saved_state_bytes = client.get(state_key) or b''
    saved_state = saved_state_bytes.decode('utf-8')
    state = get_state_from_checks(checks)
    success = is_checks_passed(checks)

    if saved_state != state or (
        success and count < SUCCESS_MAX_ATTEMPS or
            not success and count < FAILED_MAX_ATTEMPS):
        message = compose_checks_message(schain_name, node, checks)
        logger.info(f'Sending checks notification with state {state}')
        send_message(message)

    count = 1 if saved_state != state else count + 1
    logger.info(f'Saving new checks state {count} {state}')
    client.mset({count_key: count, state_key: state})


def compose_balance_message(node_info, balance, required_balance):
    if balance < required_balance:
        header = f'{EXCLAMATION_MARK} Balance on node is too low \n'
    else:
        header = f'{GREEN_LIGHT} Node id: has enough balance \n'
    return [
        header,
        f'Node id: {node_info["node_id"]}',
        f'Node ip: {node_info["node_ip"]}',
        f'Balance: {balance} ETH',
        f'Required: {required_balance} ETH'
    ]


@notifications_enabled
def notify_balance(node_info, balance, required_balance, *, client=None):
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


def compose_repair_mode_notification(node_info, schain):
    header = f'{EXCLAMATION_MARK} Repair mode for {schain} enabled \n'
    return [
        header,
        f'Node id: {node_info["node_id"]}',
        f'Node ip: {node_info["node_ip"]}',
    ]


@notifications_enabled
def notify_repair_mode(node_info, schain):
    message = compose_repair_mode_notification(node_info, schain)
    logger.info('Sending repair mode notificaton')
    send_message(message)


def send_message(message, api_key=TG_API_KEY, chat_id=TG_CHAT_ID):
    message.extend([
        f'Timestamp: {int(time.time())}',
        f'Datetime: {datetime.utcnow().ctime()}'
    ])
    plain_message = '\n'.join(message)
    return send_message_to_telegram.delay(api_key, chat_id, plain_message)
