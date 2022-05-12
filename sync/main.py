#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022 SKALE Labs
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

from skale import Skale, SkaleIma

from core.schains.monitor.sync_node_monitor import SyncNodeMonitor
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.firewall import get_default_rule_controller

from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.ima import ImaData

from tools.str_formatters import arguments_list_string
from tools.docker_utils import DockerUtils

from web.models.schain import upsert_schain_record

logger = logging.getLogger(__name__)


def monitor_sync_node(
    skale: Skale,
    skale_ima: SkaleIma,
    schain_name: str,
    node_config: NodeConfig,
    dutils: DockerUtils = None
):
    logger.info(arguments_list_string({
        'sChain name': schain_name
        }, 'Running sync node monitor'))

    schain = skale.schains.get_by_name(schain_name)

    rotation_data = skale.node_rotation.get_rotation(schain_name)
    sync_agent_ranges = get_sync_agent_ranges(skale)

    rc = get_default_rule_controller(
        name=schain_name,
        sync_agent_ranges=sync_agent_ranges
    )

    dutils = DockerUtils(volume_driver='local', host='unix:///var/run/docker.sock')  # TODO: TMP!

    schain_record = upsert_schain_record(schain_name)
    checks = SChainChecks(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rc,
        rotation_id=rotation_data['rotation_id'],
        ima_linked=False,
        dutils=dutils
    )

    ima_data = ImaData(
        linked=False,
        chain_id=skale_ima.web3.eth.chainId
    )

    monitor = SyncNodeMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        checks=checks,
        rule_controller=rc,
        dutils=dutils,
        sync_node=True
    )
    monitor.run()
