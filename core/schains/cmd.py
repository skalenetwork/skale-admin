#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022-Present SKALE Labs
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

from core.schains.config.helper import get_schain_ports
from core.schains.config.env_params import get_static_schain_cmd
from core.schains.ssl import get_ssl_filepath
from core.schains.config.directory import schain_config_filepath
from tools.configs.containers import DATA_DIR_CONTAINER_PATH, SHARED_SPACE_CONTAINER_PATH
from tools.configs import SGX_SERVER_URL
from tools.configs.ima import IMA_ENDPOINT


def get_schain_container_cmd(
    schain_name: str,
    public_key: str = None,
    start_ts: int = None,
    enable_ssl: bool = True
) -> str:
    """Returns parameters that will be passed to skaled binary in the sChain container"""
    opts = get_schain_container_base_opts(schain_name, enable_ssl=enable_ssl)
    if public_key:
        sync_opts = get_schain_container_sync_opts(start_ts)
        opts.extend(sync_opts)
    return ' '.join(opts)


def get_schain_container_sync_opts(start_ts: int = None) -> list:
    sync_opts = [
        '--download-snapshot readfromconfig',  # TODO: remove in the next version
    ]
    if start_ts:
        sync_opts.append(f'--start-timestamp {start_ts}')
    return sync_opts


def get_schain_container_base_opts(schain_name: str,
                                   enable_ssl: bool = True) -> list:
    config_filepath = schain_config_filepath(schain_name, in_schain_container=True)
    ssl_key, ssl_cert = get_ssl_filepath()
    ports = get_schain_ports(schain_name)
    static_schain_cmd = get_static_schain_cmd()
    cmd = [
        f'--config {config_filepath}',
        f'-d {DATA_DIR_CONTAINER_PATH}',
        f'--ipcpath {DATA_DIR_CONTAINER_PATH}',
        f'--http-port {ports["http"]}',
        f'--https-port {ports["https"]}',
        f'--ws-port {ports["ws"]}',
        f'--wss-port {ports["wss"]}',
        f'--sgx-url {SGX_SERVER_URL}',
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data',
        f'--main-net-url {IMA_ENDPOINT}'
    ]

    if static_schain_cmd:
        cmd.extend(static_schain_cmd)

    if enable_ssl:
        cmd.extend([
            f'--ssl-key {ssl_key}',
            f'--ssl-cert {ssl_cert}'
        ])
    return cmd
