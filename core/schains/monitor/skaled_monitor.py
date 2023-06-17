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
from typing import Optional

from core.schains.monitor.base_monitor import IMonitor
from core.schains.checks import SkaledChecks
from core.schains.monitor.action import SkaledActionManager
from core.schains.config import get_number_of_secret_shares
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
        logger.info('Monitor type %s:', typename)
        self.am._upd_last_seen()
        self.am._upd_schain_record()
        self.execute()
        self.am.log_executed_blocks()
        self.am._upd_last_seen()
        logger.info('Finished %s monitor runner', typename)


class RegularSkaledMonitor(BaseSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container()
        if not self.checks.ima_container:
            self.am.ima_container()


class RepairSkaledMonitor(BaseSkaledMonitor):
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
        if self.checks.volume and not self.checks.skaled_container:
            self.am.skaled_container(download_snapshot=True)


class BackupSkaledMonitor(BaseSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.am.skaled_container:
            self.am.skaled_container(download_snapshot=True)
        if not self.checks.rpc:
            self.am.skaled_rpc()
        if not self.checks.ima_container:
            self.am.ima_container()


class RecreateSkaledMonitor(BaseSkaledMonitor):
    def execute(self) -> None:
        logger.info('Reload requested. Recreating sChain container')
        self.am.reloaded_skaled_container()


class AfterExitTimeSkaledMonitor(BaseSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.config_updated:
            self.am.update_config()
        if self.checks.config and not self.checks.firewall_rules:
            self.am.firewall_rules()
        self.am.reloaded_skaled_container()


class NewConfigSkaledMonitor(BaseSkaledMonitor):
    def execute(self):
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.skaled_container:
            self.am.skaled_container()
        if not self.checks.rpc:
            self.am.skaled_rpc()
        if not self.checks.ima_container:
            self.am.ima_container()
        # TODO Prevent exit requests from spamming
        self.am.send_exit_request()


class NoConfigMonitor(BaseSkaledMonitor):
    def execute(self):
        if not self.am.update_config():
            logger.info('Waiting for upstream config')


class NewNodeMonitor(BaseSkaledMonitor):
    def execute(self):
        if not self.checks.config_updated:
            self.am.update_config()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.am.skaled_container:
            self.am.skaled_container(
                download_snapshot=True,
                start_ts=self.am.finish_ts
            )
        if not self.checks.ima_container:
            self.am.ima_container()


def is_backup_mode(schain_record: SChainRecord, backup_run: bool) -> bool:
    return schain_record.first_run and not schain_record.new_schain and backup_run


def is_repair_mode(
    schain_record: SChainRecord,
    checks: SkaledChecks,
    skaled_status: Optional[SkaledStatus]
) -> bool:
    return schain_record.repair_mode or is_skaled_repair_status(checks, skaled_status)


def is_new_config(checks: SkaledChecks) -> bool:
    return checks.config and not checks.config_updated


def is_exit_time_reached(checks: SkaledChecks, skaled_status: Optional[SkaledStatus]) -> bool:
    if not skaled_status:
        return False
    skaled_status.log()
    return not checks.skaled_container.status and skaled_status.exit_time_reached


def is_reload_mode(schain_record: SChainRecord) -> bool:
    return schain_record.needs_reload


def is_new_node_mode(schain_record: SChainRecord, finish_ts: int) -> bool:
    ts = int(time.time())
    secret_shares = get_number_of_secret_shares(schain_record.name)
    return finish_ts > ts and secret_shares == 1


def is_skaled_repair_status(checks: SkaledChecks, skaled_status: Optional[SkaledStatus]) -> bool:
    if skaled_status is None:
        return False
    skaled_status.log()
    needs_repair = skaled_status.clear_data_dir and skaled_status.start_from_snapshot
    return not checks.skaled_container.status and needs_repair


def is_skaled_reload_status(checks: SkaledChecks, skaled_status: Optional[SkaledStatus]) -> bool:
    if skaled_status is None:
        return False
    skaled_status.log()
    needs_reload = skaled_status.start_again and not skaled_status.start_from_snapshot
    return not checks.skaled_container.status and needs_reload


def get_skaled_monitor(
    action_manager: SkaledActionManager,
    checks: SkaledChecks,
    schain_record: SChainRecord,
    skaled_status: Optional[SkaledStatus],
    backup_run: bool = False
) -> BaseSkaledMonitor:
    mon_type = RegularSkaledMonitor
    if not checks.config:
        mon_type = NoConfigMonitor
    if is_backup_mode(schain_record, backup_run):
        mon_type = BackupSkaledMonitor
    elif is_repair_mode(schain_record, checks, skaled_status):
        mon_type = RepairSkaledMonitor
    elif is_new_node_mode(schain_record, action_manager.upstream_finish_ts):
        mon_type = NewNodeMonitor
    elif is_exit_time_reached(checks, skaled_status):
        mon_type = AfterExitTimeSkaledMonitor
    elif is_new_config(checks):
        mon_type = NewConfigSkaledMonitor
    elif is_reload_mode(schain_record):
        mon_type = RecreateSkaledMonitor

    return mon_type(
        action_manager=action_manager,
        checks=checks
    )
