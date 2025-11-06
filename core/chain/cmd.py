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

from typing import Optional

from core.chain.ssl import get_ssl_filepath
from core.config.endpoint import get_chain_ports_from_config
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.main import get_skaled_container_config_path
from core.config.schain.static_params import get_static_schain_cmd, get_static_skaled_cmd_fair
from tools.configs.containers import (
    DATA_DIR_CONTAINER_PATH,
    SHARED_SPACE_CONTAINER_PATH,
)
from tools.configs.sgx import SGX_SERVER_URL
from tools.configs.web3 import ENDPOINT
from tools.helper import is_fair


def get_skaled_container_cmd(
    chain_name: str,
    start_ts: int | None = None,
    download_snapshot: bool = False,
    enable_ssl: bool = True,
    passive_node: bool = False,
    snapshot_from: Optional[str] = None,
) -> str:
    """Returns parameters that will be passed to skaled binary in the Chain container"""
    opts = get_chain_container_base_opts(
        chain_name, enable_ssl=enable_ssl, passive_node=passive_node
    )
    if snapshot_from:
        opts.extend(['--no-snapshot-majority', snapshot_from])
    if download_snapshot:
        snapshot_opts = get_snapshot_opts(start_ts)
        opts.extend(snapshot_opts)
    return ' '.join(opts)


def get_snapshot_opts(start_ts: int | None = None) -> list:
    snapshot_opts = ['--download-snapshot readfromconfig']
    if start_ts:
        snapshot_opts.append(f'--start-timestamp {start_ts}')
    return snapshot_opts


def get_chain_container_base_opts(
    chain_name: str, enable_ssl: bool = True, passive_node: bool = False
) -> list:
    config_filepath = get_skaled_container_config_path(chain_name)
    ssl_key, ssl_cert = get_ssl_filepath()
    config = ConfigFileManager(chain_name=chain_name).skaled_config
    ports = get_chain_ports_from_config(config)

    static_chain_cmd = None
    if is_fair():
        static_chain_cmd = get_static_skaled_cmd_fair()
    else:
        static_chain_cmd = get_static_schain_cmd()

    cmd = [
        f'--config {config_filepath}',
        f'-d {DATA_DIR_CONTAINER_PATH}',
        f'--ipcpath {DATA_DIR_CONTAINER_PATH}',
        f'--http-port {ports["http"]}',
        f'--https-port {ports["https"]}',
        f'--ws-port {ports["ws"]}',
        f'--wss-port {ports["wss"]}',
    ]

    if not is_fair():
        cmd.append(f'--main-net-url {ENDPOINT}')

    if not passive_node:
        cmd.extend(
            [
                f'--sgx-url {SGX_SERVER_URL}',
                f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data',
            ]
        )

    if static_chain_cmd:
        cmd.extend(static_chain_cmd)

    if enable_ssl:
        cmd.extend([f'--ssl-key {ssl_key}', f'--ssl-cert {ssl_cert}'])
    return cmd
