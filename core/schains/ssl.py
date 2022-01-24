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
from tools.configs import SSL_CERTIFICATES_FILEPATH


def is_ssl_folder_empty(ssl_path=SSL_CERTIFICATES_FILEPATH):
    return len(os.listdir(SSL_CERTIFICATES_FILEPATH)) == 0


def get_ssl_filepath():
    if is_ssl_folder_empty():
        return 'NULL', 'NULL'
    else:
        return os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key'), \
            os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
