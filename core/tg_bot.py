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

from datetime import datetime

from telegram import Bot
from tools.configs.tg import TG_API_KEY, TG_CHAT_ID


class TgBot():
    def __init__(self, api_key=TG_API_KEY, chat_id=TG_CHAT_ID):
        self.__api_key = api_key
        self.__chat_id = chat_id
        self.bot = Bot(api_key)

    def send_message(self, formatted_message):
        return self.bot.send_message(chat_id=self.__chat_id, text=formatted_message)

    def get_emojis_for_checks(self, checks):
        checks_emojis = checks.copy()
        for check in checks:
            checks_emojis[check] = '\u2705' if checks[check] else '\u274C'
        return checks_emojis

    def send_failed_dkg_notification(self, shcain_name):
        msg = (
            f'\u2757 DKG failed'
            f'sChain name: {shcain_name}'
        )
        return self.send_message(msg)

    def send_schain_checks(self, checks, raw=False):
        checks_dict = checks.get_all()
        current_time = datetime.utcnow()
        if raw:
            message = {
                'schain_name': checks.name,
                'node_id': checks.node_id,
                'checks': checks_dict,
                'time': current_time
            }
        else:
            checks_dict = self.get_emojis_for_checks(checks_dict)

            message = (
                f'\u2757 Checks failed \n\n'
                f'Node ID: {checks.node_id}\n'
                f'sChain name: {checks.name}\n'
                f'Time (UTC): {current_time}\n\n'

                f'Data directory: {checks_dict["data_dir"]}\n'
                f'DKG: {checks_dict["dkg"]}\n'
                f'Config: {checks_dict["config"]}\n'
                f'Volume: {checks_dict["volume"]}\n'
                f'Container: {checks_dict["container"]}\n'
                f'IMA container: {checks_dict["ima_container"]}\n'
                f'Firewall: {checks_dict["firewall_rules"]}\n'
                f'RPC: {checks_dict["rpc"]}\n'
            )
        return self.send_message(message)
