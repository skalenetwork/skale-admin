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

import logging

from core.nginx.manager import NginxContainer
from core.nginx.params import is_rpc_proxy_enabled
from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


def target_rpc_proxy_mode(current: bool, dutils: DockerUtils | None = None) -> bool:
    """Moving behind nginx needs it running, leaving follows only the flag"""
    enabled = is_rpc_proxy_enabled()
    if current or not enabled:
        return enabled
    if not NginxContainer(dutils=dutils).is_running():
        logger.warning('RPC proxy is on but nginx is not running, skaled keeps the public ports')
        return False
    return True


def is_rpc_proxy_mode_changed(chain_record, dutils: DockerUtils | None = None) -> bool:
    """The running container uses other ports than the ones it should use now"""
    current = bool(chain_record.rpc_proxy_mode)
    return current != target_rpc_proxy_mode(current, dutils=dutils)
