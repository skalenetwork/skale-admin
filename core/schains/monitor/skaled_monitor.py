#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
import time
from abc import abstractmethod
from typing import Dict, Optional, Type

from core.schains.monitor.base_monitor import IMonitor
from core.schains.checks import SkaledChecks
from core.schains.monitor.action import SkaledActionManager
from core.schains.config.main import get_number_of_secret_shares
from core.schains.skaled_status import SkaledStatus
from web.models.schain import SChainRecord


logger = logging.getLogger(__name__)


class BaseSkaledMonitor(IMonitor):
    def __init__(
        self,
        action_manager: SkaledActionManager,
        checks: SkaledChecks
    ) -> None:
        self.am = action_manager
        self.checks = checks

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info('Skaled monitor type %s starting', typename)
        self.am._upd_last_seen()
        self.execute()
        self.am._upd_schain_record()
        self.am.log_executed_blocks()
        self.am._upd_last_seen()
        logger.info('Skaled monitor type %s finished', typename)


class RegularSkaledMonitor(BaseSkaledMonitor):

    def execute(self) -> None:
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container()
        else:
            self.am.reset_restart_counter()
        if not self.checks.rpc:
            self.am.skaled_rpc()
        if not self.checks.ima_container:
            self.am.ima_container()


class RepairSkaledMonitor(BaseSkaledMonitor):
    """
    When node-cli or skaled requested repair mode -
    remove volume and download snapshot
    """

    def execute(self) -> None:
        logger.warning(
            'Repair mode execution, record: %s, exit_code_ok: %s',
            self.checks.schain_record.repair_mode,
            self.checks.exit_code_ok.status
        )
        self.am.notify_repair_mode()
        self.am.cleanup_schain_docker_entity()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container(download_snapshot=True)
        else:
            self.am.reset_restart_count()
        self.am.disable_repair_mode()


class BackupSkaledMonitor(BaseSkaledMonitor):
    """
    When skaled monitor run after backup for the first time -
    download snapshot
    """

    def execute(self) -> None:
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.skaled_container:
            self.am.skaled_container(download_snapshot=True)
        else:
            self.am.reset_restart_counter()
        if not self.checks.ima_container:
            self.am.ima_container()
        self.am.disable_backup_run()


class RecreateSkaledMonitor(BaseSkaledMonitor):
    """
    When recreate requested from node-cli (currently only for new SSL certs) -
    safely remove skaled container and start again
    """

    def execute(self) -> None:
        logger.info('Reload requested. Recreating sChain container')
        if not self.checks.volume:
            self.am.volume()
        self.am.reloaded_skaled_container()


class UpdateConfigSkaledMonitor(BaseSkaledMonitor):
    """
    If config is outdated, skaled container exited and ExitTimeReached true -
    sync config with upstream and restart skaled container
    """

    def execute(self) -> None:
        if not self.checks.config_updated:
            self.am.update_config()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        self.am.reloaded_skaled_container()
        if not self.checks.ima_container:
            self.am.restart_ima_container()


class NewConfigSkaledMonitor(BaseSkaledMonitor):
    """
    When config is outdated request setExitTime with latest finish_ts from config
    """

    def execute(self):
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container(restart_on_exit=False)
        else:
            self.am.reset_restart_counter()
        if not self.checks.rpc:
            self.am.skaled_rpc()
        if not self.checks.ima_container:
            self.am.ima_container()
        self.am.send_exit_request()


class NoConfigSkaledMonitor(BaseSkaledMonitor):
    """
    When there is no skaled config - sync with upstream
    assuming it's exists
    """

    def execute(self):
        if self.checks.upstream_exists:
            logger.info('Creating skaled config')
            self.am.update_config()
        else:
            logger.debug('Waiting for upstream config')


class NewNodeSkaledMonitor(BaseSkaledMonitor):
    """
    When finish_ts is in the future and there is only one secret key share -
    download snapshot and shedule start after finish_ts
    """

    def execute(self):
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.skaled_container:
            self.am.skaled_container(
                download_snapshot=True,
                start_ts=self.am.finish_ts
            )
        else:
            self.am.reset_restart_counter()
        if not self.checks.ima_container:
            self.am.ima_container()


def is_backup_mode(schain_record: SChainRecord) -> bool:
    return schain_record.backup_run and not schain_record.new_schain


def is_repair_mode(
    schain_record: SChainRecord,
    status: Dict,
    skaled_status: Optional[SkaledStatus]
) -> bool:
    return schain_record.repair_mode or is_skaled_repair_status(status, skaled_status)


def is_new_config_mode(
    status: Dict,
    finish_ts: Optional[int]
) -> bool:
    ts = int(time.time())
    if finish_ts is None:
        return False
    return finish_ts > ts and status['config'] and not status['config_updated']


def is_config_update_time(
    status: Dict,
    skaled_status: Optional[SkaledStatus]
) -> bool:
    if not skaled_status:
        return False
    return not status['config_updated'] and \
        not status['skaled_container'] and \
        skaled_status.exit_time_reached


def is_recreate_mode(schain_record: SChainRecord) -> bool:
    return schain_record.needs_reload


def is_new_node_mode(schain_record: SChainRecord, finish_ts: Optional[int]) -> bool:
    ts = int(time.time())
    secret_shares_number = get_number_of_secret_shares(schain_record.name)
    if finish_ts is None:
        return False
    return finish_ts > ts and secret_shares_number == 1


def is_skaled_repair_status(status: Dict, skaled_status: Optional[SkaledStatus]) -> bool:
    if skaled_status is None:
        return False
    skaled_status.log()
    needs_repair = skaled_status.clear_data_dir and skaled_status.start_from_snapshot
    return not status['skaled_container'] and needs_repair


def no_config(status: Dict) -> bool:
    return not status['config']


def get_skaled_monitor(
    action_manager: SkaledActionManager,
    status: Dict,
    schain_record: SChainRecord,
    skaled_status: SkaledStatus
) -> Type[BaseSkaledMonitor]:
    logger.info('Choosing skaled monitor')
    if skaled_status:
        skaled_status.log()

    mon_type: Type[BaseSkaledMonitor] = RegularSkaledMonitor
    if no_config(status):
        mon_type = NoConfigSkaledMonitor
    elif is_backup_mode(schain_record):
        mon_type = BackupSkaledMonitor
    elif is_repair_mode(schain_record, status, skaled_status):
        mon_type = RepairSkaledMonitor
    elif is_recreate_mode(schain_record):
        mon_type = RecreateSkaledMonitor
    elif is_new_node_mode(schain_record, action_manager.finish_ts):
        mon_type = NewNodeSkaledMonitor
    elif is_config_update_time(status, skaled_status):
        mon_type = UpdateConfigSkaledMonitor
    elif is_new_config_mode(status, action_manager.finish_ts):
        mon_type = NewConfigSkaledMonitor

    return mon_type
