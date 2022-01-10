#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
import functools
from filelock import FileLock

from tools.helper import read_json, write_json


logger = logging.getLogger(__name__)


def config_setter(config_path, lock_path):
    def real_decorator(func):
        @functools.wraps(func)
        def wrapper_decorator(*args, **kwargs):
            field_name, field_value = func(*args, **kwargs)
            lock = FileLock(lock_path)
            with lock:
                config = read_json(config_path)
                config[field_name] = field_value
                write_json(config_path, config)
        return wrapper_decorator
    return real_decorator


def config_getter(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        field_name, filepath = func(*args, **kwargs)
        if not os.path.isfile(filepath):
            logger.warning("File %s is not found, can't get %s", filepath, field_name)
            return
        config = read_json(filepath)
        return config.get(field_name)
    return wrapper_decorator
