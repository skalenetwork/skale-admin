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

from skale import FairManager
from skale.core.settings import FairBaseSettings, FairSettings, get_settings
from skale.utils.web3_utils import get_endpoint
from skale.wallets import BaseWallet

from core.config.endpoint import get_local_chain_http_endpoint_from_config
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.static_params import get_fair_chain_name
from core.node_config import NodeConfig
from tools.exceptions import LocalEndpointUnreachableError
from tools.wallet_utils import init_wallet

logger = logging.getLogger(__name__)


def get_local_skaled_endpoint_fair() -> str | None:
    st = get_settings()
    chain_name = get_fair_chain_name(st.env_type)
    cfm = ConfigFileManager(chain_name=chain_name)
    if cfm.skaled_config:
        local_endpoint = get_local_chain_http_endpoint_from_config(cfm.skaled_config)
        logger.info(f'Found local skaled endpoint: {local_endpoint}')
        return local_endpoint
    return None


def get_fair_endpoints() -> list[str]:
    st = get_settings((FairBaseSettings, FairSettings))
    endpoints = [str(st.endpoint)]
    local_endpoint = get_local_skaled_endpoint_fair()
    if local_endpoint:
        endpoints.insert(0, local_endpoint)
    logger.info(f'Using endpoints for Fair: {endpoints}')
    return endpoints


def init_fair_manager(
    node_config: NodeConfig | None = None, wallet: BaseWallet | None = None
) -> FairManager:
    endpoints = get_fair_endpoints()
    endpoint = get_endpoint(endpoints)
    st = get_settings((FairBaseSettings, FairSettings))
    if node_config:
        st = get_settings(FairSettings)
        wallet = init_wallet(
            node_config=node_config, endpoint=endpoint, sgx_server_url=str(st.sgx_url)
        )
    return FairManager(endpoints, st.contracts.fair, wallet=wallet)


def init_local_fair(
    node_config: NodeConfig | None = None, wallet: BaseWallet | None = None
) -> FairManager:
    local_endpoint = get_local_skaled_endpoint_fair()
    if not local_endpoint:
        raise LocalEndpointUnreachableError(
            'Local skaled endpoint is not found, cannot initialize FairManager'
        )
    if node_config:
        wallet = init_wallet(
            node_config=node_config,
            endpoint=local_endpoint,
            sgx_server_url=str(get_settings(FairSettings).sgx_url),
        )
    return FairManager(
        local_endpoint, get_settings((FairSettings, FairBaseSettings)).contracts.fair, wallet=wallet
    )
