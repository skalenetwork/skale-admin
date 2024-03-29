#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019-Present SKALE Labs
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
from dataclasses import dataclass

from skale import Skale
from skale.schain_config.generator import get_schain_nodes_with_schains
from skale.schain_config.rotation_history import get_previous_schain_groups

from etherbase_predeployed import ETHERBASE_ADDRESS
from marionette_predeployed import MARIONETTE_ADDRESS

from core.schains.config.skale_manager_opts import SkaleManagerOpts, init_skale_manager_opts
from core.schains.config.skale_section import SkaleConfig, generate_skale_section
from core.schains.config.predeployed import generate_predeployed_accounts
from core.schains.config.precompiled import generate_precompiled_accounts
from core.schains.config.generation import Gen
from core.schains.config.helper import get_chain_id, get_schain_id
from core.schains.limits import get_schain_type

from tools.helper import read_json
from tools.configs.schains import BASE_SCHAIN_CONFIG_FILEPATH
from tools.helper import is_zero_address, is_address_contract

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


def get_on_chain_owner(schain: dict, generation: int, is_owner_contract: bool) -> str:
    """
    Returns on-chain owner depending on sChain generation.
    """
    if not is_owner_contract:
        return schain['mainnetOwner']
    if generation >= Gen.ONE:
        return MARIONETTE_ADDRESS
    if generation == Gen.ZERO:
        return schain['mainnetOwner']


def get_on_chain_etherbase(schain: dict, generation: int) -> str:
    """
    Returns on-chain owner depending on sChain generation.
    """
    if generation >= Gen.ONE:
        return ETHERBASE_ADDRESS
    if generation == Gen.ZERO:
        return schain['mainnetOwner']


def get_schain_id_for_chain(schain_name: str, generation: int) -> int:
    """
    Returns schain_id depending on sChain generation.
    """
    if generation >= Gen.TWO:
        return get_schain_id(schain_name)
    if generation >= Gen.ZERO:
        return 1


def get_schain_originator(schain: dict):
    """
    Returns address that will be used as an sChain originator
    """
    if is_zero_address(schain['originator']):
        return schain['mainnetOwner']
    return schain['originator']


def generate_schain_config(
    schain: dict, node_id: int, node: dict, ecdsa_key_name: str,
    schains_on_node: list, rotation_id: int, schain_nodes_with_schains: list,
    node_groups: list, generation: int, is_owner_contract: bool,
    skale_manager_opts: SkaleManagerOpts
) -> SChainConfig:
    """Main function that is used to generate sChain config"""
    logger.info(
        f'Going to generate sChain config for {schain["name"]}, '
        f'node_name: {node["name"]}, node_id: {node_id}, rotation_id: {rotation_id}, '
        f'ecdsa keyname: {ecdsa_key_name}'
    )

    on_chain_etherbase = get_on_chain_etherbase(schain, generation)
    on_chain_owner = get_on_chain_owner(schain, generation, is_owner_contract)
    mainnet_owner = schain['mainnetOwner']
    schain_type = get_schain_type(schain['partOfNode'])

    schain_id = get_schain_id_for_chain(schain['name'], generation)

    base_config = SChainBaseConfig(BASE_SCHAIN_CONFIG_FILEPATH)

    dynamic_params = {
        'chainID': get_chain_id(schain['name'])
    }

    originator_address = get_schain_originator(schain)

    predeployed_accounts = generate_predeployed_accounts(
        schain_name=schain['name'],
        schain_type=schain_type,
        schain_nodes=schain_nodes_with_schains,
        on_chain_owner=on_chain_owner,
        mainnet_owner=mainnet_owner,
        originator_address=originator_address,
        generation=generation
    )

    precompiled_accounts = generate_precompiled_accounts(
        on_chain_owner=on_chain_owner
    )

    skale_config = generate_skale_section(
        schain=schain,
        on_chain_etherbase=on_chain_etherbase,
        on_chain_owner=on_chain_owner,
        schain_id=schain_id,
        node_id=node_id,
        node=node,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        schain_nodes_with_schains=schain_nodes_with_schains,
        rotation_id=rotation_id,
        node_groups=node_groups,
        skale_manager_opts=skale_manager_opts
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
            **predeployed_accounts,
            **precompiled_accounts,
        },
        skale_config=skale_config
    )
    return schain_config


def generate_schain_config_with_skale(
    skale: Skale,
    schain_name: str,
    generation: int,
    node_id: int,
    rotation_data: dict,
    ecdsa_key_name: str
) -> SChainConfig:
    schain_nodes_with_schains = get_schain_nodes_with_schains(skale, schain_name)
    schains_on_node = skale.schains.get_schains_for_node(node_id)
    schain = skale.schains.get_by_name(schain_name)
    node = skale.nodes.get(node_id)
    node_groups = get_previous_schain_groups(skale, schain_name)

    is_owner_contract = is_address_contract(skale.web3, schain['mainnetOwner'])

    skale_manager_opts = init_skale_manager_opts(skale)

    return generate_schain_config(
        schain=schain,
        node=node,
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        schains_on_node=schains_on_node,
        rotation_id=rotation_data['rotation_id'],
        schain_nodes_with_schains=schain_nodes_with_schains,
        node_groups=node_groups,
        generation=generation,
        is_owner_contract=is_owner_contract,
        skale_manager_opts=skale_manager_opts
    )
