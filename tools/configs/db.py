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

import os
from tools.configs import NODE_DATA_PATH

# mysql db

MYSQL_DB_USER = os.environ["DB_USER"]
MYSQL_DB_PASSWORD = os.environ["DB_PASSWORD"]
MYSQL_DB_NAME = 'db_skale'
MYSQL_DB_HOST = '127.0.0.1'
MYSQL_DB_PORT = int(os.environ["DB_PORT"])

# sqlite db

DB_FILENAME = 'skale.db'
DB_FILE = os.path.join(NODE_DATA_PATH, DB_FILENAME)
