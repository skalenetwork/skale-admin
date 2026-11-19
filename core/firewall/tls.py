#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026-Present SKALE Labs
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

from pathlib import Path

from filelock import FileLock

from core.firewall.base.nftables import NFTablesCmdFailedError, NFTablesController
from tools.constants import NFT_CHAIN_BASE_PATH


def open_tls_ports() -> None:
    """Open node TLS services in the set provisioned by node-cli and persist it"""
    path = Path(NFT_CHAIN_BASE_PATH) / 'tls-ports.conf'
    with FileLock(path.with_suffix('.lock'), timeout=120):
        controller = NFTablesController(chain='tls')
        rc, _, error = controller.run_cmd('add element inet firewall skale_tls_ports { 443, 311 }')
        if rc != 0:
            raise NFTablesCmdFailedError(f'Failed to open TLS ports: {error}')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(
            'set skale_tls_ports { type inet_service; elements = { 443, 311 }; }\n'
        )
        temporary.replace(path)
