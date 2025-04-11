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
import time

MAX_ALLOWED_LOG_TIME_DIFF = os.getenv('MAX_ALLOWED_LOG_TIME_DIFF', 600)
ADMIN_LOG_FILEPATH = os.getenv('ADMIN_LOG_FILEPATH', '/skale_node_data/log/admin.log')


def run_healthcheck():
    modification_time = os.path.getmtime(ADMIN_LOG_FILEPATH)
    current_time = time.time()
    time_diff = current_time - modification_time

    print(f'Modification time diff: {time_diff}, limit is {MAX_ALLOWED_LOG_TIME_DIFF}')
    if time_diff > int(MAX_ALLOWED_LOG_TIME_DIFF):
        exit(3)
    else:
        exit(0)


if __name__ == '__main__':
    run_healthcheck()
