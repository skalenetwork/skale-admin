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

import hashlib
import logging
import re
import sys
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler

from tools.configs.logs import (ADMIN_LOG_PATH,
                                API_LOG_PATH,
                                DEBUG_LOG_PATH,
                                LOG_FILE_SIZE_BYTES,
                                LOG_BACKUP_COUNT, LOG_FORMAT)


HIDING_PATTERNS = [
    r'NEK\:\w+',
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
    r'ws[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
]


class HidingFormatter:
    def __init__(self, base_formatter, patterns):
        self.base_formatter = base_formatter
        self._patterns = patterns

    @classmethod
    def convert_match_to_sha3(cls, match):
        return hashlib.sha3_256(match.group(0).encode('utf-8')).digest().hex()

    def format(self, record):
        msg = self.base_formatter.format(record)
        for pattern in self._patterns:
            pat = re.compile(pattern)
            msg = pat.sub(self.convert_match_to_sha3, msg)
        return msg

    def __getattr__(self, attr):
        return getattr(self.base_formatter, attr)


def init_logger(log_file_path, debug_file_path=None):
    handlers = []

    base_formatter = Formatter(LOG_FORMAT)
    formatter = HidingFormatter(base_formatter, HIDING_PATTERNS)
    f_handler = RotatingFileHandler(log_file_path, maxBytes=LOG_FILE_SIZE_BYTES,
                                    backupCount=LOG_BACKUP_COUNT)

    f_handler.setFormatter(formatter)
    f_handler.setLevel(logging.INFO)
    handlers.append(f_handler)

    stream_handler = StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    handlers.append(stream_handler)

    if debug_file_path:
        f_handler_debug = RotatingFileHandler(debug_file_path,
                                              maxBytes=LOG_FILE_SIZE_BYTES,
                                              backupCount=LOG_BACKUP_COUNT)
        f_handler_debug.setFormatter(formatter)
        f_handler_debug.setLevel(logging.DEBUG)
        handlers.append(f_handler_debug)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers)


def init_admin_logger():
    init_logger(ADMIN_LOG_PATH, DEBUG_LOG_PATH)


def init_api_logger():
    init_logger(API_LOG_PATH)
