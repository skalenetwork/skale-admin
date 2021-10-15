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

import json
import shutil
import logging
from dataclasses import dataclass

from skale import Skale
from skale.schain_config.generator import get_schain_nodes_with_schains

from core.node import get_skale_node_version
from core.schains.config.skale_config import SkaleConfig, generate_skale_config
from core.schains.config.accounts import generate_dynamic_accounts
from core.schains.config.helper import get_chain_id
from core.schains.config.dir import get_tmp_schain_config_filepath

from core.schains.config.dir import schain_config_filepath
from tools.helper import read_json
from tools.configs.schains import BASE_SCHAIN_CONFIG_FILEPATH
from tools.str_formatters import arguments_list_string

from web.models.schain import upsert_schain_record


logger = logging.getLogger(__name__)


class NoBaseConfigError(Exception):
    pass


class SChainBaseConfig:
    """Wrapper for the static part of sChain config"""
    def __init__(self, base_config_path):
        self._base_config_path = base_config_path
        self.read()

    def read(self):
        logger.debug(f'Reading sChain base config: {self._base_config_path}')
        try:
            self.config = read_json(self._base_config_path)
        except Exception as err:
            raise NoBaseConfigError(err)


@dataclass
class SChainConfig:
    """Dataclass that represents a full sChain configuration"""
    seal_engine: str
    params: dict
    unddos: dict
    genesis: dict
    accounts: dict
    skale_config: SkaleConfig

    def to_dict(self):
        """Returns camel-case representation of the SChainConfig object"""
        return {
            'sealEngine': self.seal_engine,
            'params': self.params,
            'unddos': self.unddos,
            'genesis': self.genesis,
            'accounts': self.accounts,
            'skaleConfig': self.skale_config.to_dict(),
        }


def generate_schain_config(schain: dict, schain_id: int, node_id: int,
                           node: dict, ecdsa_key_name: str, schains_on_node: list,
                           rotation_id: int, schain_nodes_with_schains: list,
                           previous_public_keys: list) -> SChainConfig:
    """Main function that is used to generate sChain config"""
    logger.info(
        f'Going to generate sChain config for {schain["name"]}, '
        f'node_name: {node["name"]}, node_id: {node_id}, rotation_id: {rotation_id}, '
        f'ecdsa keyname: {ecdsa_key_name}, schain_id: {schain_id}'
    )

    base_config = SChainBaseConfig(BASE_SCHAIN_CONFIG_FILEPATH)

    dynamic_params = {
        'chainID': get_chain_id(schain['name'])
    }

    dynamic_accounts = generate_dynamic_accounts(
        schain=schain,
        schain_nodes=schain_nodes_with_schains
    )

    skale_config = generate_skale_config(
        schain=schain,
        schain_id=schain_id,
        node_id=node_id,
        node=node,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        schain_nodes_with_schains=schain_nodes_with_schains,
        rotation_id=rotation_id,
        previous_public_keys=previous_public_keys
    )

    schain_config = SChainConfig(
        seal_engine=base_config.config['sealEngine'],
        params={
            **base_config.config['params'],
            **dynamic_params
        },
        unddos=base_config.config['unddos'],
        genesis=base_config.config['genesis'],
        accounts={
            **base_config.config['accounts'],
            **dynamic_accounts
        },
        skale_config=skale_config
    )
    return schain_config


def generate_schain_config_with_skale(skale: Skale, schain_name: str, node_id: int,
                                      rotation_id: int, ecdsa_key_name: str) -> SChainConfig:
    schain_id = 1  # todo: remove this later (should be removed from the skaled first)
    schain_nodes_with_schains = get_schain_nodes_with_schains(skale, schain_name)
    schains_on_node = skale.schains.get_schains_for_node(node_id)
    schain = skale.schains.get_by_name(schain_name)

    group_id = skale.schains.name_to_group_id(schain_name)
    previous_public_keys = skale.key_storage.get_all_previous_public_keys(group_id)

    node = skale.nodes.get(node_id)

    return generate_schain_config(
        schain=schain,
        schain_id=schain_id,
        node=node,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        schain_nodes_with_schains=schain_nodes_with_schains,
        previous_public_keys=previous_public_keys
    )


def init_schain_config(
    skale,
    node_id,
    schain_name,
    ecdsa_sgx_key_name,
    rotation_id,
    schain_record
):
    config_filepath = schain_config_filepath(schain_name)

    logger.warning(arguments_list_string({
        'sChain name': schain_name,
        'config_filepath': config_filepath
        }, 'Generating sChain config'))

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        node_id=node_id,
        rotation_id=rotation_id,
        ecdsa_key_name=ecdsa_sgx_key_name
    )
    save_schain_config(schain_config.to_dict(), schain_name)
    update_schain_config_version(schain_name, schain_record=schain_record)


def save_schain_config(schain_config, schain_name):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    with open(tmp_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)
    config_filepath = schain_config_filepath(schain_name)
    shutil.move(tmp_config_filepath, config_filepath)


def update_schain_config_version(schain_name, schain_record=None):
    new_config_version = get_skale_node_version()
    schain_record = schain_record or upsert_schain_record(schain_name)
    logger.info(f'Going to change config_version for {schain_name}: \
{schain_record.config_version} -> {new_config_version}')
    schain_record.set_config_version(new_config_version)


def schain_config_version_match(schain_name, schain_record=None):
    schain_record = schain_record or upsert_schain_record(schain_name)
    skale_node_version = get_skale_node_version()
    logger.debug(f'config check, schain: {schain_name}, config_version: \
{schain_record.config_version}, skale_node_version: {skale_node_version}')
    return schain_record.config_version == skale_node_version
