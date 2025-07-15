#   -*- coding: utf-8 -*-
#
#  This file is part of SKALE Admin
#
#   Copyright (C) 2025-Present SKALE Labs
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

from skale import MirageManager
from skale.utils.web3_utils import get_endpoint
from skale.wallets import BaseWallet

from core.config.endpoint import get_local_chain_http_endpoint_from_config
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.static_params import get_mirage_chain_name
from core.node_config import NodeConfig
from tools.configs.web3 import boot_endpoint, mirage_contracts
from tools.exceptions import LocalEndpointUnreachableError
from tools.wallet_utils import init_wallet

logger = logging.getLogger(__name__)


def get_local_skaled_endpoint_mirage() -> str | None:
    chain_name = get_mirage_chain_name()
    cfm = ConfigFileManager(chain_name=chain_name)
    if cfm.skaled_config:
        local_endpoint = get_local_chain_http_endpoint_from_config(cfm.skaled_config)
        logger.info(f'Found local skaled endpoint: {local_endpoint}')
        return local_endpoint
    return None


def get_mirage_endpoints() -> list[str]:
    endpoints = [boot_endpoint()]
    local_endpoint = get_local_skaled_endpoint_mirage()
    if local_endpoint:
        endpoints.insert(0, local_endpoint)
    logger.info(f'Using endpoints for Mirage: {endpoints}')
    return endpoints


def init_mirage_manager(
    node_config: NodeConfig | None = None, wallet: BaseWallet | None = None
) -> MirageManager:
    endpoints = get_mirage_endpoints()
    endpoint = get_endpoint(endpoints)
    if node_config:
        wallet = init_wallet(node_config=node_config, endpoint=endpoint)
    return MirageManager(endpoints, mirage_contracts(), wallet=wallet)


def init_local_mirage(
    node_config: NodeConfig | None = None, wallet: BaseWallet | None = None
) -> MirageManager:
    local_endpoint = get_local_skaled_endpoint_mirage()
    if not local_endpoint:
        raise LocalEndpointUnreachableError(
            'Local skaled endpoint is not found, cannot initialize MirageManager'
        )
    if node_config:
        wallet = init_wallet(node_config=node_config, endpoint=local_endpoint)
    return MirageManager(local_endpoint, mirage_contracts(), wallet=wallet)
