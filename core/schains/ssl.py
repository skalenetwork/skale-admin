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
import logging
from datetime import datetime

from web.models.schain import SChainRecord
from tools.configs import SSL_CERTIFICATES_FILEPATH, SSL_CERT_PATH


logger = logging.getLogger(__name__)


def is_ssl_folder_empty(ssl_path=SSL_CERTIFICATES_FILEPATH):
    return len(os.listdir(ssl_path)) == 0


def get_ssl_filepath():
    if is_ssl_folder_empty():
        return 'NULL', 'NULL'
    else:
        return os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key'), \
            os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')


def get_ssl_files_change_date() -> datetime:
    if is_ssl_folder_empty():
        return
    ssl_changed_ts = os.path.getmtime(SSL_CERT_PATH)
    return datetime.utcfromtimestamp(ssl_changed_ts)


def update_ssl_change_date(schain_record: SChainRecord) -> bool:
    ssl_files_change_date = get_ssl_files_change_date()
    if not ssl_files_change_date:
        logger.warning(
            f'Tried to update SSL change date for {schain_record.name}, but no SSL files found')
        return False
    schain_record.set_ssl_change_date(ssl_files_change_date)
    return True


def ssl_reload_needed(schain_record: SChainRecord) -> bool:
    ssl_files_change_date = get_ssl_files_change_date()
    if not ssl_files_change_date:
        logger.warning(
            f'Tried to get SSL change date for {schain_record.name}, but no SSL files found')
        return False
    logger.info(f'ssl_files_change_date: {ssl_files_change_date}, \
ssl_change_date for chain {schain_record.name}: {schain_record.ssl_change_date}')
    return ssl_files_change_date != schain_record.ssl_change_date
