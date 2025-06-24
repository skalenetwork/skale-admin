#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

from skale.types.node import NodeId

from core.checks.base import BaseSkaledChecks, CheckRes, IChecks
from core.config.schain.file_manager import ConfigFileManager
from core.redis.chain_record import ChainRecord
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.types.chain import MirageChainName
from tools.resources import get_statsd_client


logger = logging.getLogger(__name__)


class MirageConfigChecks(IChecks):
    def __init__(
        self,
        chain_name: MirageChainName,
        node_id: NodeId,
        group_index: int,
        stream_version: str,
        chain_record: ChainRecord,
    ) -> None:
        self.name = chain_name
        self.node_id = node_id
        self.chain_record = chain_record
        self.group_index = group_index
        self.stream_version = stream_version
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=chain_name)
        self.statsd_client = get_statsd_client()

    def get_name(self) -> str:
        return self.name

    @property
    def config_dir(self) -> CheckRes:
        """Checks that sChain config directory exists"""
        dir_path = self.cfm.dirname
        return CheckRes(os.path.isdir(dir_path))

    @property
    def dkg(self) -> CheckRes:
        """Checks that DKG procedure is completed"""
        secret_key_share_filepath = get_secret_key_share_filepath(self.name, self.group_index)
        return CheckRes(os.path.isfile(secret_key_share_filepath))

    @property
    def upstream_config(self) -> CheckRes:
        """
        Returns True if config exists for current rotation id,
        node ip addresses and stream version are up to date
        and config regeneration was not triggered manually.
        Returns False otherwise.
        """
        exists = self.cfm.upstream_exist_for_rotation_id(self.group_index)
        logger.debug('Upstream configs status for %s: %s', self.name, exists)
        stream_updated = self.chain_record.config_version == self.stream_version
        triggered = self.chain_record.sync_config_run

        logger.info(
            'Upstream config status, group_index %s: exist: %s,stream: %s, triggered: %s',
            self.group_index,
            exists,
            stream_updated,
            triggered,
        )
        return CheckRes(exists and stream_updated and not triggered)


class SkaledChecks(BaseSkaledChecks):
    @property
    def firewall_rules(self) -> CheckRes:
        return CheckRes(status=True, data={})  # todod: implement firewall rules check
