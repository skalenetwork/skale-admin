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
from abc import abstractmethod
from typing import Optional

from core.schains.monitor.base_monitor import IMonitor
from core.schains.checks import SkaledChecks
from core.schains.monitor.action import SkaledActionManager
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
        self.p = self.am.p
        self.checks = checks

    @abstractmethod
    def run(self) -> None:
        pass


class RegularSkaledMonitor(BaseSkaledMonitor):
    def run(self) -> None:
        if self.checks.config or self.am.update_config():
            if not self.checks.firewall_rules:
                self.am.firewall_rules()
            if not self.checks.volume:
                self.am.volume()
            if self.checks.volume and not self.checks.skaled_container:
                self.am.skaled_container()


class RepairSkaledMonitor(BaseSkaledMonitor):
    def run(self) -> None:
        if self.checks.config or self.am.update_config():
            if not self.checks.firewall:
                self.am.firewall()
            if not self.checks.volume:
                self.am.volume()
            if self.checks.volume and not self.checks.skaled_container:
                self.am.skaled_container()


class BackupSkaledMonitor(BaseSkaledMonitor):
    def run(self) -> None:
        if self.checks.config or self.am.update_config():
            if not self.checks.volume:
                self.am.volume()
            if not self.checks.firewall:
                self.am.firewall_rules()
            if not self.skaled_container:
                self.am.skaled_container(download_snapshot=True)
            if not self.checks.rpc:
                self.am.skaled_rpc()
            if not self.ima_container:
                self.am.ima_container()


class RecreateSkaledMonitor(BaseSkaledMonitor):
    def run(self) -> None:
        logger.info(
            '%s. Reload requested. Going to restart sChain container',
            self.p
        )
        self.am.reloaded_skaled_container()


class AfterExitTimeSkaledMonitor(BaseSkaledMonitor):
    def run(self) -> None:
        if not self.checks.config_updated:
            self.am.update_config()
        if self.checks.upstream_config and not self.checks.firewall:
            self.am.firewall_rules()
        self.am.reloaded_skaled_container()


class NewConfigSkaledMonitor(BaseSkaledMonitor):
    # IVD should only be run for node rotation cases / or get timestamp for ip change.
    def run(self):
        if self.checks.config and not self.checks.firewall:
            self.am.firewall_rules()
        if not self.checks.skaled_container:
            self.am.skaled_container()
        if not self.checks.rpc:
            self.am.skaled_rpc()
        if not self.checks.ima_container:
            self.am.ima_container()
        # IVD TODO Send exit only once
        self.am.send_exit_request()


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
    if is_backup_mode(schain_record, backup_run):
        mon_type = BackupSkaledMonitor
    if is_repair_mode(schain_record, checks, skaled_status):
        mon_type = RepairSkaledMonitor
    if is_new_config(checks):
        mon_type = NewConfigSkaledMonitor
    if is_exit_time_reached(checks, skaled_status):
        mon_type = AfterExitTimeSkaledMonitor
    elif is_reload_mode(schain_record):
        mon_type = RecreateSkaledMonitor

    return mon_type(
        action_manager=action_manager,
        checks=checks
    )
