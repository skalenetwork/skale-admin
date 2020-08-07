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

import logging
from dataclasses import dataclass

from core.schains.config.contract_settings import (ContractSettings,
                                                   generate_schain_contract_settings)
from core.schains.config.accounts import generate_dynamic_accounts
from core.schains.config.helper import get_chain_id

from tools.helper import read_json
from tools.configs.schains import BASE_SCHAIN_CONFIG_FILEPATH


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
class NodeInfo:
    """Dataclass that represents nodeInfo key of the skaleConfig section"""

    def to_dict(self):
        """Returns camel-case representation of the NodeInfo object"""
        return {
            # todo: 3030
        }


@dataclass
class SChainInfo:
    """Dataclass that represents sChain key of the skaleConfig section"""

    def to_dict(self):
        """Returns camel-case representation of the SChainInfo object"""
        return {
            # todo: 3030
        }


@dataclass
class SkaleConfig:
    """Dataclass that represents skaleConfig key of the sChain config"""
    contract_settings: ContractSettings
    node_info: NodeInfo
    schain_info: SChainInfo

    def to_dict(self):
        """Returns camel-case representation of the SkaleConfig object"""
        return {
            'contractSettings': self.contract_settings.to_dict(),
            'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


@dataclass
class SChainConfig:
    """Dataclass that represents a full sChain configuration"""
    seal_engine: str
    params: dict
    genesis: dict
    accounts: dict
    skale_config: SkaleConfig

    def to_dict(self):
        """Returns camel-case representation of the SChainConfig object"""
        return {
            'sealEngine': self.seal_engine,
            'params': self.params,
            'genesis': self.genesis,
            'accounts': self.accounts,
            'skale_config': self.skale_config.to_dict(),
        }


def generate_schain_config():
    """Main function that is used to generate sChain config"""
    logger.info(f'Going to generate sChain config...')

    schain_owner = '0x5112cE768917E907191557D7E9521c2590Cdd3A0'  # todo: 3030 tmp
    schain_nodes_owners = ['0x278Af5dD8523e54d0Ce37e27b3cbcc6A3368Ddeb',
                           '0x5112cE768917E907191557D7E9521c2590Cdd3A0']  # todo: 3030 tmp
    schain_name = 'test'  # todo: 3030 tmp
    schain_internal_limits = {'maxFileStorageBytes': 128}  # todo: 3030 tmp

    base_config = SChainBaseConfig(BASE_SCHAIN_CONFIG_FILEPATH)

    contract_settings = generate_schain_contract_settings(
        schain_owner=schain_owner,
        schain_nodes_owners=schain_nodes_owners
    )
    node_info = NodeInfo()
    schain_info = SChainInfo()

    skale_config = SkaleConfig(
        contract_settings=contract_settings,
        node_info=node_info,
        schain_info=schain_info,
    )

    dynamic_params = {
        'chainID': get_chain_id(schain_name)
    }

    dynamic_accounts = generate_dynamic_accounts(
        schain_owner=schain_owner,
        schain_nodes_owners=schain_nodes_owners,
        schain_name=schain_name,
        schain_internal_limits=schain_internal_limits
    )

    schain_config = SChainConfig(
        seal_engine=base_config.config['sealEngine'],
        params={
            **base_config.config['params'],
            **dynamic_params
        },
        genesis=base_config.config['genesis'],
        accounts={
            **base_config.config['accounts'],
            **dynamic_accounts
        },
        skale_config=skale_config
    )
    return schain_config
