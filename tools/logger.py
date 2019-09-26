#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import sys
import logging
from logging import FileHandler, Formatter, StreamHandler
import logging.handlers as py_handlers

from tools.config import ADMIN_LOG_PATH, BUILD_LOG_PATH, DEBUG_LOG_PATH, LOG_FILE_SIZE_BYTES, LOG_BACKUP_COUNT, LOG_FORMAT


def init_logger(log_file_path, debug_file_path=None):
    handlers = []

    formatter = Formatter(LOG_FORMAT)
    f_handler = py_handlers.RotatingFileHandler(log_file_path, maxBytes=LOG_FILE_SIZE_BYTES, backupCount=LOG_BACKUP_COUNT)

    f_handler.setFormatter(formatter)
    f_handler.setLevel(logging.INFO)
    handlers.append(f_handler)

    stream_handler = StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    handlers.append(stream_handler)

    if debug_file_path:
        f_handler_debug = py_handlers.RotatingFileHandler(debug_file_path, maxBytes=LOG_FILE_SIZE_BYTES,
                                                          backupCount=LOG_BACKUP_COUNT)
        f_handler_debug.setFormatter(formatter)
        f_handler_debug.setLevel(logging.DEBUG)
        handlers.append(f_handler_debug)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers)


def init_build_logger():
    init_logger(BUILD_LOG_PATH)


def init_admin_logger():
    init_logger(ADMIN_LOG_PATH, DEBUG_LOG_PATH)
