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
import time
from datetime import datetime

from tools.notifications.tasks import send_message_to_telegram

# IVD TMP
# from tools.configs.tg import TG_API_KEY, TG_CHAT_ID
TG_API_KEY = ''
TG_CHAT_ID = ''

RED_LIGHT = '\u274C'
GREEN_LIGHT = '\u2705'
EXCLAMATION_MARK = '\u2757'


def convert_bool_to_emoji_lights(checks):
    checks_emojis = copy.deepcopy(checks)
    for check in checks:
        checks_emojis[check] = GREEN_LIGHT if checks[check] else RED_LIGHT
    return checks_emojis


def compose_failed_checks_message(schain_name, node_id, checks, raw=False):
    if raw:
        message = {
            'schain_name': schain_name,
            'node_id': node_id,
            'checks': checks,
        }
    else:
        formated_checks = convert_bool_to_emoji_lights(checks)

        message = (
            f'{EXCLAMATION_MARK} Checks failed \n\n'
            f'Node ID: {node_id}\n'
            f'sChain name: {schain_name}\n'
            f'Data directory: {formated_checks["data_dir"]}\n'
            f'DKG: {formated_checks["dkg"]}\n'
            f'Config: {formated_checks["config"]}\n'
            f'Volume: {formated_checks["volume"]}\n'
            f'Container: {formated_checks["container"]}\n'
            # f'IMA container: {formated_checks["ima_container"]}\n'
            f'Firewall: {formated_checks["firewall_rules"]}\n'
            f'RPC: {formated_checks["rpc"]}\n'
        )
    return message


def notifications_enabled():
    return TG_API_KEY and TG_CHAT_ID


def notify_failed_checks(schain_name, node_id, checks):
    message = compose_failed_checks_message(schain_name, node_id, checks)
    send_message(message)


def send_message(message, api_key=TG_API_KEY, chat_id=TG_CHAT_ID):
    message['timestamp'] = int(time.time())
    message['datetime'] = datetime.utcnow()
    return send_message_to_telegram.delay(api_key, chat_id, message)
