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

from tools.helper import read_json
from tools.configs.schains import FILESTORAGE_ARTIFACTS_FILEPATH


FILESTORAGE_LIMIT_OPTION_NAME = 'max_file_storage_bytes'


def get_filestorage_info():
    return read_json(FILESTORAGE_ARTIFACTS_FILEPATH)


def compose_filestorage_info(schain_internal_limits, schain_owner):
    predeployed_config = get_filestorage_info()['predeployedConfig']
    max_file_storage_bytes = schain_internal_limits[FILESTORAGE_LIMIT_OPTION_NAME]
    filestorage_info = {
        'implementation': predeployed_config['filestorageImplementation']
    }
    upgradeable_info = compose_filestorage_upgradeable_info(predeployed_config,
                                                            max_file_storage_bytes,
                                                            schain_owner)
    filestorage_info.update(upgradeable_info)
    return filestorage_info


def compose_filestorage_upgradeable_info(predeployed_info, allocated_storage, schain_owner):
    proxy_admin = predeployed_info['proxyAdmin']
    filestorage_proxy = predeployed_info['filestorageProxy']
    proxy_admin_owner_slot = '0x0'
    allocated_storage_slot = '0x0'
    proxy_admin['storage'][proxy_admin_owner_slot] = schain_owner
    filestorage_proxy['storage'][allocated_storage_slot] = str(allocated_storage)
    return {
        'proxy_admin': proxy_admin,
        'proxy': filestorage_proxy
    }
