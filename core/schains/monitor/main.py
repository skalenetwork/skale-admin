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

import time
import logging
from importlib import reload

from web3._utils import request

from core.node_config import NodeConfig
from core.schains.monitor import RegularMonitor
from core.schains.checks import SChainChecks

from tools.docker_utils import DockerUtils
from web.models.schain import upsert_schain_record


logger = logging.getLogger(__name__)


def get_log_prefix(name):
    return f'schain: {name} -'


def run_monitor_for_schain(skale, skale_ima, node_config: NodeConfig, schain):
    p = get_log_prefix(schain["name"])
    try:
        logger.info(f'{p} monitor created')
        reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)

        name = schain["name"]
        dutils = DockerUtils()

        while True:
            ima_linked = skale_ima.linker.has_schain(name)
            rotation_id = skale.schains.get_last_rotation_id(name)

            schain_record = upsert_schain_record(name)
            checks = SChainChecks(
                name,
                node_config.id,
                schain_record=schain_record,
                rotation_id=rotation_id,
                ima_linked=ima_linked,
                dutils=dutils
            )

            # todo: determine monitor type here

            monitor = RegularMonitor(
                skale=skale,
                schain=schain,
                node_config=node_config,
                rotation_id=rotation_id,
                checks=checks
            )
            monitor.run()
            time.sleep(30)  # todo: change sleep interval

    except Exception:
        logger.exception(f'{p} monitor failed')
