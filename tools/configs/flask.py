#   -*- coding: utf-8 -*-
#
#   This file is part of skale-admin
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

HERE = os.path.dirname(os.path.realpath(__file__))
EVENTS_POLL_INTERVAL = 5

FLASK_APP_HOST = os.environ['FLASK_APP_HOST']
FLASK_APP_PORT = int(os.environ['FLASK_APP_PORT'])

SKALE_LIB_NAME = 'skale.py'


