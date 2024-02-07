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
import re
import sys
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

from flask import has_request_context, request

from tools.configs import SGX_SERVER_URL
from tools.configs.logs import (
    ADMIN_LOG_FORMAT,
    ADMIN_LOG_PATH,
    API_LOG_FORMAT, API_LOG_PATH,
    SYNC_LOG_FORMAT, SYNC_LOG_PATH,
    DEBUG_LOG_PATH,
    LOG_FILE_SIZE_BYTES,
    LOG_BACKUP_COUNT
)
from tools.configs.web3 import ENDPOINT


def compose_hiding_patterns():
    sgx_ip = urlparse(SGX_SERVER_URL).hostname
    eth_ip = urlparse(ENDPOINT).hostname
    return {
        rf'{sgx_ip}': '[SGX_IP]',
        rf'{eth_ip}': '[ETH_IP]',
        r'NEK\:\w+': '[SGX_KEY]'
    }


class RequestFormatter(logging.Formatter):
    def format(self, record):
        if not isinstance(record, str):
            if has_request_context():
                record.url = request.full_path[:-1]
            else:
                record.url = None
        return super().format(record)


class HidingFormatter(RequestFormatter):
    def __init__(self, log_format: str, patterns: dict) -> None:
        super().__init__(log_format)
        self._patterns: dict = patterns

    def _filter_sensitive(self, msg) -> str:
        for match, replacement in self._patterns.items():
            pat = re.compile(match)
            msg = pat.sub(replacement, msg)
        return msg

    def format(self, record) -> str:
        msg = super().format(record)
        return self._filter_sensitive(msg)

    def formatException(self, exc_info) -> str:
        msg = super().formatException(exc_info)
        return self._filter_sensitive(msg)

    def formatStack(self, stack_info) -> str:
        msg = super().formatStack(stack_info)
        return self._filter_sensitive(msg)


def init_logger(
    log_format,
    log_file_path=None,
    debug_file_path=None
):
    # for handler in logging.root.handlers[:]:
    #    logging.root.removeHandler(handler)

    handlers = []

    hiding_patterns = compose_hiding_patterns()
    formatter = HidingFormatter(log_format, hiding_patterns)
    if log_file_path:
        f_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=LOG_FILE_SIZE_BYTES,
            backupCount=LOG_BACKUP_COUNT
        )

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
    init_logger(ADMIN_LOG_FORMAT, ADMIN_LOG_PATH, DEBUG_LOG_PATH)


def init_api_logger():
    init_logger(API_LOG_FORMAT, API_LOG_PATH)


def init_sync_logger():
    init_logger(SYNC_LOG_FORMAT, SYNC_LOG_PATH)
