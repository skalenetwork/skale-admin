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


def get_default_cert_location():
    ssl_dirs_dirs = os.listdir(SSL_CERTIFICATES_FILEPATH)
    if len(ssl_dirs_dirs) > 0:
        return os.path.join(SSL_CERTIFICATES_FILEPATH, ssl_dirs_dirs[0])


def get_ssl_filepath():
    cert_location_path = get_default_cert_location()
    if not cert_location_path or not os.path.exists(cert_location_path):
        return 'NULL', 'NULL'
    else:
        return os.path.join(cert_location_path, 'ssl_key'), os.path.join(cert_location_path,
                                                                         'ssl_cert')
