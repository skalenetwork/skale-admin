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

import os, json, logging
logger = logging.getLogger(__name__)

class ConfigStorage:
    def __init__(self, path, init={}):
        self.path = path
        self.init = init
        self.config = self.__safe_read_config()

    def __getitem__(self, item):
        return self.config[item]

    def __setitem__(self, key, value):
        self.config[key] = value
        self.update(self.config)

    def update_item_field(self, key, field, value):
        item = self.config[key]
        item[field] = value
        self.config[key] = item
        self.update(self.config)

    def update(self, new_config):
        config = self._read_config()
        config.update(new_config)
        self.config = config
        self._write_config(config)
        return config

    def get(self):
        return self.config

    def safe_get(self, item):
        try:
            return self.config[item]
        except KeyError:
            logger.debug(f'key {item} is not found in config {self.path}')
            return None

    def __safe_read_config(self):
        if not self.__check_config_file():
            self.__init_config_file()
        return self._read_config()

    def _read_config(self):
        with open(self.path, encoding='utf-8') as data_file:
            config = json.loads(data_file.read())
        return config

    def _write_config(self, config):
        with open(self.path, 'w') as data_file:
            json.dump(config, data_file, indent=2)

    def __check_config_file(self):
        return os.path.exists(self.path)

    def __init_config_file(self):
        self._write_config(self.init)
