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
from urllib.parse import parse_qsl, urlparse

from flask import has_request_context, request
from skale_core.settings import BaseNodeSettings, FairSettings, SkaleSettings, get_settings

from tools.constants.logs import (
    ADMIN_LOG_FORMAT,
    ADMIN_LOG_PATH,
    API_LOG_FORMAT,
    API_LOG_PATH,
    DEBUG_LOG_PATH,
    FAIR_LOG_FORMAT,
    LOG_BACKUP_COUNT,
    LOG_FILE_SIZE_BYTES,
)
from tools.helper import is_fair, is_passive

LOCAL_IPS = ['127.0.0.1', 'localhost']

# URL path segments and query values shorter than this are considered too generic
# to be secrets (masking short words like 'mainnet' would garble unrelated log text)
SECRET_PATH_SEGMENT_MIN_LENGTH = 16
SECRET_QUERY_VALUE_MIN_LENGTH = 12

GENERIC_HIDING_PATTERNS = {
    r'NEK\:\w+': '[SGX_KEY]',
    r'(?i)([?&](?:auth|token|apikey|api_key)=)[^&\s,\'"]+': r'\1[HIDDEN]',
}


def compose_url_hiding_patterns(url: str, label: str) -> dict:
    parsed = urlparse(url)
    patterns = {}
    if parsed.query:
        patterns[re.escape(parsed.query)] = f'[{label}_QUERY]'
        for _, value in parse_qsl(parsed.query, keep_blank_values=False):
            if len(value) >= SECRET_QUERY_VALUE_MIN_LENGTH:
                patterns[re.escape(value)] = f'[{label}_QUERY_VALUE]'
    if parsed.password:
        patterns[re.escape(parsed.password)] = f'[{label}_PASSWORD]'
    for segment in (parsed.path or '').split('/'):
        if len(segment) >= SECRET_PATH_SEGMENT_MIN_LENGTH:
            patterns[re.escape(segment)] = f'[{label}_PATH_SEGMENT]'
    if parsed.hostname and parsed.hostname not in LOCAL_IPS:
        patterns[re.escape(parsed.hostname)] = f'[{label}_IP]'
    return patterns


def compose_hiding_patterns():
    patterns = {}
    if not is_passive():
        sgx_url = str(get_settings((SkaleSettings, FairSettings)).sgx_url)
        patterns.update(compose_url_hiding_patterns(sgx_url, 'SGX'))
    if not is_fair():
        eth_url = str(get_settings((BaseNodeSettings, SkaleSettings)).endpoint)
        patterns.update(compose_url_hiding_patterns(eth_url, 'ETH'))
    patterns.update(GENERIC_HIDING_PATTERNS)
    return patterns


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


def init_logger(log_format, log_file_path=None, debug_file_path=None):
    handlers = []

    hiding_patterns = compose_hiding_patterns()
    formatter = HidingFormatter(log_format, hiding_patterns)
    if log_file_path:
        f_handler = RotatingFileHandler(
            log_file_path, maxBytes=LOG_FILE_SIZE_BYTES, backupCount=LOG_BACKUP_COUNT
        )

        f_handler.setFormatter(formatter)
        f_handler.setLevel(logging.INFO)
        handlers.append(f_handler)

    stream_handler = StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    handlers.append(stream_handler)

    if debug_file_path:
        f_handler_debug = RotatingFileHandler(
            debug_file_path, maxBytes=LOG_FILE_SIZE_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        f_handler_debug.setFormatter(formatter)
        f_handler_debug.setLevel(logging.DEBUG)
        handlers.append(f_handler_debug)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers)


def init_admin_logger():
    init_logger(ADMIN_LOG_FORMAT, ADMIN_LOG_PATH, DEBUG_LOG_PATH)


def init_fair_logger():
    init_logger(FAIR_LOG_FORMAT, ADMIN_LOG_PATH, DEBUG_LOG_PATH)


def init_api_logger():
    init_logger(API_LOG_FORMAT, API_LOG_PATH)
