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

import os
import logging
from celery import Celery
from telegram import Bot

from tools.configs.db import REDIS_URI


# No more than 20 per minute
NOTIFICATIONS_RATE_LIMIT = os.getenv('NOTIFICATIONS_RATE_LIMIT', '20/m')

logger = logging.getLogger(__name__)

app = Celery('tasks', broker=REDIS_URI)

SEND_MSG_TIMEOUT = 30


@app.task(rate_limit=NOTIFICATIONS_RATE_LIMIT)
def send_message_to_telegram(api_key, chat_id, message, bot=None):
    bot = bot or Bot(api_key)
    logger.info(f'Sending message to telegram {message}')
    return bot.send_message(
        chat_id=chat_id,
        text=message,
        timeout=SEND_MSG_TIMEOUT
    )
