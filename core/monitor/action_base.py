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

import abc
import logging
import time
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from core.chain.rpc import handle_failed_skaled_rpc
from core.chain.runner import get_container_name, is_container_exists
from core.chain.status import init_skaled_status
from core.checks.base import BaseSkaledChecks
from core.config.schain.file_manager import ConfigFileManager
from core.firewall import IRuleController
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.schains.cleaner import remove_schain_volume, remove_skaled_container
from core.schains.exit_scheduler import ExitScheduleFileManager
from core.types.chain import ChainName
from tools.constants.containers import SKALED_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import is_passive
from tools.node_options import NodeOptions
from tools.notifications.messages import notify_repair_mode
from tools.resources import get_statsd_client
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseActionManager(abc.ABC):
    def __init__(self, name: ChainName, post_run_delay: int = CONTAINER_POST_RUN_DELAY):
        self.name = name
        self.post_run_delay = post_run_delay
        self.executed_blocks: Dict = {}

    @staticmethod
    def monitor_block(f):
        @wraps(f)
        def _monitor_block(self, *args, **kwargs):
            ts = time.time()
            initial_status = f(self, *args, **kwargs)
            te = time.time()
            self.executed_blocks[f.__name__] = {
                'ts': ts,
                'te': te,
                'initial_status': initial_status,
            }
            return initial_status

        return _monitor_block

    @property
    @abc.abstractmethod
    def chain_record(self) -> SChainRecord | ChainRecord:
        pass

    def _upd_last_seen(self) -> None:
        self.chain_record.set_monitor_last_seen(datetime.now())

    def _upd_chain_record(self) -> None:
        if self.chain_record.first_run:
            self.chain_record.set_restart_count(0)
            self.chain_record.set_failed_rpc_count(0)
        self.chain_record.set_first_run(False)

        logger.info(
            'restart_count - %s, failed_rpc_count - %s',
            self.chain_record.restart_count,
            self.chain_record.failed_rpc_count,
        )

    def log_executed_blocks(self) -> None:
        logger.info(
            arguments_list_string(self.executed_blocks, f'finish_monitor_runner - {self.name}')
        )


class BaseSkaledActionManager(BaseActionManager):
    def __init__(
        self,
        chain_name: ChainName,
        rule_controller: IRuleController,
        checks: BaseSkaledChecks,
        node_config: NodeConfig,
        dutils: DockerUtils | None = None,
        node_options: NodeOptions | None = None,
        post_run_delay: int = CONTAINER_POST_RUN_DELAY,
        schain_cleanup_timeout: int = SCHAIN_CLEANUP_TIMEOUT,
    ):
        self.chain_name = chain_name
        self.checks = checks
        self.node_config = node_config
        self.rule_controller = rule_controller
        self.schain_cleanup_timeout = schain_cleanup_timeout

        self.skaled_status = init_skaled_status(chain_name)
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=self.chain_name)

        self.esfm = ExitScheduleFileManager(chain_name)
        self.dutils = dutils or DockerUtils()
        self.statsd_client = get_statsd_client()

        self.node_options = node_options or NodeOptions()

        super().__init__(name=chain_name, post_run_delay=post_run_delay)

    @property
    def chain_record(self) -> ChainRecord:
        return ChainRecord(name=self.chain_name)

    @BaseActionManager.monitor_block
    @abc.abstractmethod
    def volume(self) -> bool:
        """Create or check volume for the chain"""

    @BaseActionManager.monitor_block
    @abc.abstractmethod
    def skaled_container(self, *args: Any, **kwargs: Any) -> bool:
        """Run monitor_skaled_container"""

    @BaseActionManager.monitor_block
    def reset_restart_counter(self) -> bool:
        self.chain_record.set_restart_count(0)
        return True

    @BaseActionManager.monitor_block
    def recreated_skaled_container(self, abort_on_exit: bool = True) -> bool:
        logger.info('Starting skaled from scratch')
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            logger.info('Removing skaled container')
            remove_skaled_container(self.name, dutils=self.dutils)
        else:
            logger.warning('Container does not exists')
        self.chain_record.set_restart_count(0)
        self.chain_record.set_failed_rpc_count(0)
        if type(self.chain_record) is ChainRecord:  # todo: remove after migration to ChainRecord
            self.chain_record.set_restart_ts(0)
        initial_status = self.skaled_container(
            abort_on_exit=abort_on_exit,
            passive_node=is_passive(),
        )
        return initial_status

    @BaseActionManager.monitor_block
    def skaled_rpc(self) -> bool:
        initial_status = self.checks.rpc.status
        if not initial_status:
            self.display_skaled_logs()
            logger.info('Handling schain rpc')
            handle_failed_skaled_rpc(
                chain_name=self.chain_name,
                chain_record=self.chain_record,
                skaled_status=self.skaled_status,
                dutils=self.dutils,
            )
        else:
            self.chain_record.set_failed_rpc_count(0)
            logger.info('rpc - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def cleanup_schain_docker_entity(self) -> bool:
        logger.info('Removing skaled docker artifacts')
        remove_skaled_container(self.name, dutils=self.dutils)
        time.sleep(self.schain_cleanup_timeout)
        remove_schain_volume(self.name, dutils=self.dutils)
        return True

    @BaseActionManager.monitor_block
    def update_config(self) -> bool:
        logger.info('Syncing skaled config with upstream')
        return self.cfm.sync_skaled_config_with_upstream()

    @property
    def upstream_config_path(self) -> Optional[str]:
        return self.cfm.latest_upstream_path

    def display_skaled_logs(self) -> None:
        if is_container_exists(self.name, dutils=self.dutils):
            container_name = get_container_name(SKALED_CONTAINER, self.name)
            self.dutils.display_container_logs(container_name)
        else:
            logger.warning(f"sChain {self.name}: container doesn't exists, could not show logs")

    @BaseActionManager.monitor_block
    def notify_repair_mode(self) -> None:
        notify_repair_mode(self.node_config.all(), self.name)

    @BaseActionManager.monitor_block
    def update_repair_ts(self, new_ts: int) -> None:
        logger.info('Setting repair_ts to %d', new_ts)
        new_dt = datetime.utcfromtimestamp(new_ts)
        self.chain_record.set_repair_date(new_dt)
