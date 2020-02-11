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

import os
import logging
from time import sleep, time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from skale.manager_client import spawn_skale_lib

from web.models.schain import SChainRecord

from tools.bls.dkg_client import DkgError
from tools.custom_thread import CustomThread
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

from core.schains.runner import run_schain_container, run_ima_container
from core.schains.cleaner import remove_config_dir, run_cleanup
from core.schains.helper import (init_schain_dir, get_schain_config_filepath)
from core.schains.config import (generate_schain_config, save_schain_config,
                                 get_schain_env, get_allowed_endpoints)
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_env
from core.schains.dkg import init_bls

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.iptables import add_rules as add_iptables_rules

from . import MONITOR_INTERVAL

logger = logging.getLogger(__name__)
dutils = DockerUtils()

CONTAINERS_DELAY = 20


class SchainsMonitor:
    def __init__(self, skale, node_config):
        self.skale = skale
        self.node_config = node_config
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        CustomThread('Wait for node ID', self.wait_for_node_id, once=True).start()

    def wait_for_node_id(self, opts):
        while self.node_config.id is None:
            logger.debug('Waiting for the node_id in sChains Monitor...')
            sleep(MONITOR_INTERVAL)
        self.node_id = self.node_config.id
        self.monitor = CustomThread('sChains monitor', self.monitor_schains,
                                    interval=MONITOR_INTERVAL)
        self.monitor.start()

    def monitor_schains(self, opts):
        skale = spawn_skale_lib(self.skale)
        schains = skale.schains_data.get_schains_for_node(self.node_id)
        leaving_history = self.skale.schains_data.get_leaving_history(self.node_id)
        for history in leaving_history:
            schain = self.skale.schains_data.get(history[0])
            if time() < schain[1] and schain['name']:
                schain['active'] = True
                schains.append(schain)
        schains_on_node = sum(map(lambda schain: schain['active'], schains))
        schains_holes = len(schains) - schains_on_node
        logger.info(
            arguments_list_string({'Node ID': self.node_id, 'sChains on node': schains_on_node,
                                   'Empty sChain structs': schains_holes}, 'Monitoring sChains'))
        threads = []
        for schain in schains:
            if not schain['active']:
                continue
            schain_thread = CustomThread(f'sChain monitor: {schain["name"]}', self.monitor_schain,
                                         opts=schain, once=True)
            schain_thread.start()
            threads.append(schain_thread)

        for thread in threads:
            thread.join()

    def monitor_schain(self, schain):
        skale = spawn_skale_lib(self.skale)
        name = schain['name']
        owner = schain['owner']
        checks = SChainChecks(skale, name, self.node_id, log=True).get_all()

        if not SChainRecord.added(name):
            schain_record, _ = SChainRecord.add(name)
        else:
            schain_record = SChainRecord.get_by_name(name)

        rotation_in_progress = checks['rotation_in_progress']['result']
        new_schain = checks['rotation_in_progress']['new_schain']
        exiting_node = checks['rotation_in_progress']['exiting_node']

        if exiting_node and rotation_in_progress:
            logger.info('Node is exiting. sChain is stopping')
            finish_time = datetime.fromtimestamp(checks['rotation_in_progress']['finish_ts'])
            jobs = sum(map(lambda job: job.name == name, self.scheduler.get_jobs()))
            if not jobs:
                self.scheduler.add_job(run_cleanup, 'date', run_date=finish_time,
                                       name=name, args=[self.skale, name, self.node_id])
            logger.info(f'sChain will be stoped at {finish_time}')
            return

        if rotation_in_progress and new_schain:
            logger.info('Building new rotated schain')
        elif rotation_in_progress and not new_schain:
            logger.info('Schain was rotated. Containers are going to be restarted')
        else:
            logger.info('No rotation for schain')

        if not checks['data_dir']['result']:
            init_schain_dir(name)
        if not checks['dkg']['result']:
            try:
                schain_record.dkg_started()
                init_bls(skale, schain['name'], self.node_config.id,
                         self.node_config.sgx_key_name)
            except DkgError as err:
                logger.info(f'sChain {name} Dkg procedure failed with {err}')
                schain_record.dkg_failed()
                remove_config_dir(schain['name'])
                exit(1)
            schain_record.dkg_done()
        if not checks['config']['result']:
            self.init_schain_config(skale, name, owner)
        if not checks['volume']['result']:
            init_data_volume(schain)
        if not checks['firewall_rules']['result']:
            self.add_firewall_rules(name)
        if not checks['container']['result']:
            self.monitor_schain_container(schain)
        sleep(CONTAINERS_DELAY)
        if not checks['ima_container']['result']:
            self.monitor_ima_container(schain)

    def init_schain_config(self, skale, schain_name, schain_owner):
        config_filepath = get_schain_config_filepath(schain_name)
        if not os.path.isfile(config_filepath):
            logger.warning(
                f'sChain {schain_name}: sChain config not found: '
                f'{config_filepath}, trying to create.'
            )
            schain_config = generate_schain_config(skale, schain_name, self.node_id)
            save_schain_config(schain_config, schain_name)

    def add_firewall_rules(self, schain_name):
        endpoints = get_allowed_endpoints(schain_name)
        add_iptables_rules(endpoints)

    def check_container(self, schain_name, volume_required=False):
        name = get_container_name(SCHAIN_CONTAINER, schain_name)
        info = dutils.get_info(name)
        if dutils.to_start_container(info):
            logger.warning(f'sChain: {schain_name}. '
                           f'sChain container: {name} not found, trying to create.')
            if volume_required and not dutils.data_volume_exists(schain_name):
                logger.error(
                    f'sChain: {schain_name}. Cannot create sChain container without data volume'
                )
            return True

    def monitor_schain_container(self, schain):
        if self.check_container(schain['name'], volume_required=True):
            env = get_schain_env(schain['name'])
            run_schain_container(schain, env)

    def monitor_ima_container(self, schain):
        env = get_ima_env(schain['name'])
        run_ima_container(schain, env)
