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

from core.schains.volume import get_filestorage_info


FILESTORAGE_LIMIT_OPTION_NAME = 'maxFileStorageBytes'


def compose_filestorage_info(schin_internal_limits):
    filestorage_info = get_filestorage_info()
    max_file_storage_bytes = schin_internal_limits[FILESTORAGE_LIMIT_OPTION_NAME]
    return {
        'address': filestorage_info['address'],
        'bytecode': filestorage_info['bytecode'],
        'storage': {
            '0x0': str(max_file_storage_bytes)
        }
    }
