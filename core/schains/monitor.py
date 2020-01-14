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
from time import sleep

from skale.manager_client import spawn_skale_lib

from web.models.schain import SChainRecord

from tools.custom_thread import CustomThread
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

from core.schains.runner import run_schain_container, run_ima_container
from core.schains.helper import (init_schain_dir, get_schain_config_filepath,
                                 get_schain_config)
from core.schains.config import (generate_schain_config, save_schain_config,
                                 get_schain_env)
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_env
from core.schains.dkg import init_bls, FailedDKG

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.iptables import add_rules as add_iptables_rules

from . import MONITOR_INTERVAL

logger = logging.getLogger(__name__)
dutils = DockerUtils()


class SchainsMonitor():
    def __init__(self, skale, node_config):
        self.skale = skale
        self.node_config = node_config
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
        checks = SChainChecks(name, self.node_id, log=True).get_all()

        if not SChainRecord.added(name):
            schain_record, _ = SChainRecord.add(name)
        else:
            schain_record = SChainRecord.get_by_name(name)

        if not checks['data_dir']:
            init_schain_dir(name)
        if not checks['dkg']:
            try:
                schain_record.dkg_started()
                init_bls(skale, schain['name'], self.node_config.id, self.node_config.sgx_key_name)
            except FailedDKG:
                schain_record.dkg_failed()
                exit(1)
            schain_record.dkg_done()
        if not checks['config']:
            self.init_schain_config(skale, name, owner)
        if not checks['volume']:
            init_data_volume(schain)
        if not checks['container']:
            self.monitor_schain_container(schain)
        if not checks['ima_container']:
            self.monitor_ima_container(schain)

    def init_schain_config(self, skale, schain_name, schain_owner):
        config_filepath = get_schain_config_filepath(schain_name)
        if not os.path.isfile(config_filepath):
            logger.warning(f'sChain config not found: {config_filepath}, trying to create.')
            schain_config = generate_schain_config(skale, schain_name, self.node_id)
            save_schain_config(schain_config, schain_name)

    def add_firewall_rules(self, schain_name):
        config = get_schain_config(schain_name)
        ips, ports = self.get_consensus_ips_with_ports(config)
        add_iptables_rules(ips, ports)

    def get_consensus_ips_with_ports(self, config):
        ips = [node_data['ip'] for node_data in config['schain_nodes']]
        ports = [node_data['basePort'] for node_data in config['schain_nodes']]
        return ips, ports

    def check_container(self, schain_name, volume_required=False):
        name = get_container_name(SCHAIN_CONTAINER, schain_name)
        info = dutils.get_info(name)
        if dutils.to_start_container(info):
            logger.warning(f'sChain container: {name} not found, trying to create.')
            if volume_required and not dutils.data_volume_exists(schain_name):
                logger.error(f'Cannot create sChain container without data volume - {schain_name}')
            return True

    def monitor_schain_container(self, schain):
        if self.check_container(schain['name'], volume_required=True):
            env = get_schain_env(schain['name'])
            run_schain_container(schain, env)

    def monitor_ima_container(self, schain):
        env = get_ima_env(schain['name'])
        run_ima_container(schain, env)
