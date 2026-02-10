#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026 SKALE Labs
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
from pathlib import Path

# path

## path - file/folder names

CONFIG_FOLDER_NAME: str = 'config'
NODE_DATA_FOLDER_NAME: str = 'node_data'
CONTRACTS_INFO_FOLDER_NAME: str = 'contracts_info'

SSL_KEY_NAME: str = 'ssl_key'
SSL_CRT_NAME: str = 'ssl_cert'

NODE_CONFIG_FILENAME = 'node_config.json'
CONTAINERS_FILENAME = 'containers.json'
IMA_MIGRATION_FILENAME = 'ima_migration_schedule.yaml'

# path - general

SKALE_VOLUME_PATH: Path = Path(os.getenv('SKALE_VOLUME_PATH', '/skale_vol'))

NODE_DATA_PATH: Path = SKALE_VOLUME_PATH / NODE_DATA_FOLDER_NAME

SCHAIN_NODE_DATA_PATH: Path = Path('/skale_node_data')
SCHAIN_CONFIG_DIR_SKALED: Path = Path('/schain_config')

CONTRACTS_INFO_FOLDER: Path = SKALE_VOLUME_PATH / CONTRACTS_INFO_FOLDER_NAME
CONFIG_FOLDER: Path = SKALE_VOLUME_PATH / CONFIG_FOLDER_NAME

CHECK_REPORT_PATH: Path = SKALE_VOLUME_PATH / 'reports' / 'checks.json'

## path - config

STATIC_ACCOUNTS_FOLDER: Path = CONFIG_FOLDER / 'schain_accounts'
STATIC_GROUPS_FOLDER: Path = CONFIG_FOLDER / 'node_groups'

STATIC_PARAMS_FILEPATH: Path = CONFIG_FOLDER / 'static_params.yaml'
FAIR_STATIC_PARAMS_FILEPATH: Path = CONFIG_FOLDER / 'fair_static_params.yaml'

CONTAINERS_FILEPATH: Path = CONFIG_FOLDER / CONTAINERS_FILENAME
IMA_MIGRATION_PATH: Path = CONFIG_FOLDER / IMA_MIGRATION_FILENAME

## path - node

NODE_CONFIG_FILEPATH: Path = NODE_DATA_PATH / NODE_CONFIG_FILENAME
INIT_LOCK_PATH: Path = NODE_DATA_PATH / 'init.lock'
META_FILEPATH: Path = NODE_DATA_PATH / 'meta.json'
NODE_OPTIONS_FILEPATH: Path = NODE_DATA_PATH / 'node_options.json'
DOCKER_NODE_CONFIG_FILEPATH = NODE_DATA_PATH / 'docker.json'

## path - ssl

SSL_CERTIFICATES_FILEPATH: Path = NODE_DATA_PATH / 'ssl'
SSL_KEY_PATH: Path = SSL_CERTIFICATES_FILEPATH / SSL_KEY_NAME
SSL_CERT_PATH: Path = SSL_CERTIFICATES_FILEPATH / SSL_CRT_NAME

## path - lib

SKALE_LIB_PATH: Path = Path('/var/lib/skale')
CHAIN_STATE_PATH: Path = SKALE_LIB_PATH / 'schains'
FILESTORAGE_STATIC_PATH: Path = SKALE_LIB_PATH / 'filestorage'

## path - settings

SETTINGS_FOLDER_PATH: Path = SKALE_VOLUME_PATH / 'settings'
NODE_SETTINGS_PATH: Path = SETTINGS_FOLDER_PATH / 'node.toml'
INTERNAL_SETTINGS_PATH: Path = SETTINGS_FOLDER_PATH / 'internal.toml'

## path - firewall

NFT_CHAIN_BASE_PATH = '/etc/nft.conf.d/skale/chains'
NFT_CHAIN_CONFIG_WILDCARD = os.path.join(NFT_CHAIN_BASE_PATH, '*')

# path - nginx

NGINX_CONTAINER_NAME: str = 'sk_nginx'
NGINX_TEMPLATE_FILEPATH: Path = CONFIG_FOLDER / 'nginx.conf.j2'
NGINX_CONFIG_FILEPATH: Path = NODE_DATA_PATH / 'nginx.conf'

# path - sgx

SGX_SSL_KEY_NAME = 'sgx.key'
SGX_SSL_CERT_NAME = 'sgx.crt'

SGX_CERTIFICATES_FOLDER = NODE_DATA_PATH / 'sgx_certs'

SGX_SSL_KEY_FILEPATH = SGX_CERTIFICATES_FOLDER / SGX_SSL_KEY_NAME
SGX_SSL_CERT_FILEPATH = SGX_CERTIFICATES_FOLDER / SGX_SSL_CERT_NAME

# path - resource allocation

RESOURCE_ALLOCATION_FILENAME = 'resource_allocation.json'
RESOURCE_ALLOCATION_FILEPATH = NODE_DATA_PATH / RESOURCE_ALLOCATION_FILENAME

# other

NESTED_DELIMITER = '__'
FILESTORAGE_LIMIT_OPTION_NAME = 'max_file_storage_bytes'
