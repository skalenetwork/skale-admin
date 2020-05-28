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
import shutil
import logging
from time import sleep

from skale.manager_client import spawn_skale_lib

from web.models.schain import SChainRecord

from tools.bls.dkg_client import DkgError
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

from core.schains.runner import run_schain_container, run_ima_container
from core.schains.cleaner import remove_config_dir
from core.tg_bot import TgBot
from core.schains.helper import (init_schain_dir, get_schain_config_filepath,
                                 get_schain_proxy_file_path)
from core.schains.config import (generate_schain_config, save_schain_config,
                                 get_schain_env, get_allowed_endpoints)
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_env
from core.schains.dkg import run_dkg

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.configs.tg import TG_API_KEY, TG_CHAT_ID
from tools.configs.schains import IMA_DATA_FILEPATH
from tools.iptables import add_rules as add_iptables_rules

from concurrent.futures import ThreadPoolExecutor
# from multiprocessing import Process

logger = logging.getLogger(__name__)
dutils = DockerUtils()

CONTAINERS_DELAY = 20


def run_creator(skale, node_config):
    monitor(skale, node_config)
    # process = Process(target=monitor, args=(skale, node_config))
    # process.start()
    # process.join()


def monitor(skale, node_config):
    logger.info('Creator procedure started')
    skale = spawn_skale_lib(skale)
    node_id = node_config.id
    schains = skale.schains_data.get_schains_for_node(node_id)
    schains_on_node = sum(map(lambda schain: schain['active'], schains))
    schains_holes = len(schains) - schains_on_node
    logger.info(
        arguments_list_string({'Node ID': node_id, 'sChains on node': schains_on_node,
                               'Empty sChain structs': schains_holes}, 'Monitoring sChains'))
    with ThreadPoolExecutor(max_workers=max(1, schains_on_node)) as executor:
        futures = [executor.submit(monitor_schain, skale, node_config.id,
                                   node_config.sgx_key_name, schain)
                   for schain in schains if schain['active']]
        for future in futures:
            future.result()
    logger.info('Creator procedure finished')


def monitor_schain(skale, node_id, sgx_key_name, schain):
    skale = spawn_skale_lib(skale)
    name = schain['name']
    owner = schain['owner']
    checks = SChainChecks(name, node_id, log=True)
    checks_dict = checks.get_all()
    bot = TgBot(TG_API_KEY, TG_CHAT_ID) if TG_API_KEY and TG_CHAT_ID else None

    if not SChainRecord.added(name):
        schain_record, _ = SChainRecord.add(name)
    else:
        schain_record = SChainRecord.get_by_name(name)

    if not schain_record.first_run:
        if bot and not checks.is_healthy():
            bot.send_schain_checks(checks)

    schain_record.set_first_run(False)

    if not checks_dict['data_dir']:
        init_schain_dir(name)
    if not checks_dict['dkg']:
        try:
            schain_record.dkg_started()
            run_dkg(skale, schain['name'], node_id, sgx_key_name)
        except DkgError as err:
            logger.info(f'sChain {name} Dkg procedure failed with {err}')
            if bot:
                bot.send_failed_dkg_notification(schain['name'])
            schain_record.dkg_failed()
            remove_config_dir(schain['name'])
            return
        schain_record.dkg_done()
    if not checks_dict['config']:
        init_schain_config(skale, node_id, name, owner)
        copy_schain_ima_abi(name)
    if not checks_dict['volume']:
        init_data_volume(schain)
    if not checks_dict['firewall_rules']:
        add_firewall_rules(name)
    if not checks_dict['container']:
        monitor_schain_container(schain)
    sleep(CONTAINERS_DELAY)
    if not checks_dict['ima_container']:
        monitor_ima_container(schain)


def init_schain_config(skale, node_id, schain_name, schain_owner):
    config_filepath = get_schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        logger.warning(
            f'sChain {schain_name}: sChain config not found: '
            f'{config_filepath}, trying to create.'
        )
        schain_config = generate_schain_config(skale, schain_name, node_id)
        save_schain_config(schain_config, schain_name)


def copy_schain_ima_abi(name):
    abi_file_dest = get_schain_proxy_file_path(name)
    shutil.copyfile(IMA_DATA_FILEPATH, abi_file_dest)


def add_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def check_container(schain_name, volume_required=False):
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


def monitor_schain_container(schain):
    if check_container(schain['name'], volume_required=True):
        env = get_schain_env(schain['name'])
        run_schain_container(schain, env)


def monitor_ima_container(schain):
    env = get_ima_env(schain['name'])
    run_ima_container(schain, env)
