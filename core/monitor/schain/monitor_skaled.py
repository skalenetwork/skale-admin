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
from typing import Dict, Optional, Type

from core.chain.ssl import ssl_reload_needed
from core.chain.status import NodeCliStatus, SkaledStatus
from core.checks.schain import SkaledChecks
from core.config.schain.main import get_number_of_secret_shares
from core.monitor.monitor_base import BaseSkaledMonitor
from core.monitor.schain.action_skaled import SkaledActionManager
from tools.helper import is_passive
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


class BaseSChainSkaledMonitor(BaseSkaledMonitor):
    def __init__(self, action_manager: SkaledActionManager, checks: SkaledChecks) -> None:
        self._am = action_manager
        self._checks = checks
        self.statsd_client = get_statsd_client()

    @property
    def am(self) -> SkaledActionManager:
        return self._am

    @property
    def checks(self) -> SkaledChecks:
        return self._checks


class RegularSkaledMonitor(BaseSChainSkaledMonitor):
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
        if not self.checks.ima_container and not is_passive():
            self.am.ima_container()


class SnapshotSkaledMonitor(BaseSChainSkaledMonitor):
    """
    Triggered only on sync node, when repair_ts is set
    """

    def execute(self) -> None:
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container(download_snapshot=True)
        else:
            self.am.reset_restart_counter()
        self.am.update_repair_ts(new_ts=int(time.time()))


class RepairSkaledMonitor(BaseSChainSkaledMonitor):
    """
    When node-cli or skaled requested repair mode -
    remove volume and download snapshot
    """

    def execute(self) -> None:
        logger.warning(
            'Repair mode execution, exit_code_ok: %s',
            self.checks.exit_code_ok.status,
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
            self.am.reset_restart_counter()
        self.am.update_repair_ts(new_ts=int(time.time()))


class BackupSkaledMonitor(BaseSChainSkaledMonitor):
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


class RecreateSkaledMonitor(BaseSChainSkaledMonitor):
    """
    When recreate requested from node-cli (currently only for new SSL certs) -
    safely remove skaled container and start again
    """

    def execute(self) -> None:
        logger.info('Reload requested. Recreating sChain container')
        if not self.checks.volume:
            self.am.volume()
        self.am.recreated_skaled_container()


class UpdateConfigSkaledMonitor(BaseSChainSkaledMonitor):
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
        self.am.reset_exit_schedule()
        self.am.recreated_chain_containers(abort_on_exit=False)


class ReloadGroupSkaledMonitor(BaseSChainSkaledMonitor):
    """
    When config is outdated set exit time to the latest finish_ts from schain config
    """

    def execute(self):
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
        self.am.schedule_skaled_exit(self.am.upstream_finish_ts)


class ReloadIpSkaledMonitor(BaseSChainSkaledMonitor):
    """
    When config is outdated set exit time to reload_ts from external config
    """

    def execute(self):
        if not self.checks.firewall_rules:
            self.am.firewall_rules(upstream=True)
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
        self.am.schedule_skaled_exit(self.am.econfig.reload_ts)


class NoConfigSkaledMonitor(BaseSChainSkaledMonitor):
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


class NewNodeSkaledMonitor(BaseSChainSkaledMonitor):
    """
    When finish_ts is in the future and there is only one secret key share -
    download snapshot and schedule start after finish_ts
    """

    def execute(self):
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.firewall_rules:
            self.am.firewall_rules()
        if not self.checks.skaled_container:
            self.am.skaled_container(download_snapshot=True, start_ts=self.am.upstream_finish_ts)
        else:
            self.am.reset_restart_counter()
        if not self.checks.ima_container:
            self.am.ima_container()


def is_backup_mode(schain_record: SChainRecord) -> bool:
    return schain_record.backup_run


def is_repair_mode(
    schain_record: SChainRecord,
    check_status: Dict,
    skaled_status: Optional[SkaledStatus],
    ncli_status: Optional[NodeCliStatus],
    automatic_repair: bool,
) -> bool:
    repair_ts = int(schain_record.repair_date.timestamp())
    if ncli_status is not None and ncli_status.repair_ts > repair_ts:
        return True
    return automatic_repair and is_skaled_repair_internal(check_status, skaled_status)


def is_reload_group_mode(check_status: Dict, finish_ts: Optional[int]) -> bool:
    ts = int(time.time())
    if finish_ts is None:
        return False
    return finish_ts > ts and check_status['config'] and not check_status['config_updated']


def is_reload_ip_mode(check_status: Dict, reload_ts: Optional[int]) -> bool:
    if reload_ts is None:
        return False
    return check_status['config'] and not check_status['config_updated']


def is_config_update_time(check_status: Dict, skaled_status: Optional[SkaledStatus]) -> bool:
    if not skaled_status:
        return False
    return not check_status['skaled_container'] and skaled_status.exit_time_reached


def is_recreate_mode(status: Dict, schain_record: SChainRecord) -> bool:
    return status['skaled_container'] and ssl_reload_needed(schain_record)


def is_new_node_mode(schain_record: SChainRecord, finish_ts: Optional[int]) -> bool:
    ts = int(time.time())
    secret_shares_number = get_number_of_secret_shares(schain_record.name)
    if finish_ts is None:
        return False
    return finish_ts > ts and secret_shares_number == 1


def is_skaled_repair_internal(check_status: Dict, skaled_status: Optional[SkaledStatus]) -> bool:
    if skaled_status is None:
        return False
    skaled_status.log()
    needs_repair = skaled_status.clear_data_dir and skaled_status.start_from_snapshot
    return not check_status['skaled_container'] and needs_repair


def no_config(check_status: Dict) -> bool:
    return not check_status['config']


def get_skaled_monitor(
    action_manager: SkaledActionManager,
    check_status: Dict,
    schain_record: SChainRecord,
    skaled_status: SkaledStatus,
    ncli_status: NodeCliStatus,
    automatic_repair: bool = True,
) -> Type[BaseSkaledMonitor]:
    logger.info('Choosing skaled monitor')
    if skaled_status:
        skaled_status.log()

    mon_type: Type[BaseSkaledMonitor] = RegularSkaledMonitor

    if is_passive():
        if no_config(check_status):
            mon_type = NoConfigSkaledMonitor
        elif is_recreate_mode(check_status, schain_record):
            mon_type = RecreateSkaledMonitor
        elif is_repair_mode(schain_record, check_status, skaled_status, ncli_status, False):
            mon_type = SnapshotSkaledMonitor
        elif is_config_update_time(check_status, skaled_status):
            mon_type = UpdateConfigSkaledMonitor
        elif is_reload_group_mode(check_status, action_manager.upstream_finish_ts):
            mon_type = ReloadGroupSkaledMonitor
        elif is_reload_ip_mode(check_status, action_manager.econfig.reload_ts):
            mon_type = ReloadIpSkaledMonitor
        return mon_type

    if no_config(check_status):
        mon_type = NoConfigSkaledMonitor
    elif is_backup_mode(schain_record):
        mon_type = BackupSkaledMonitor
    elif is_repair_mode(schain_record, check_status, skaled_status, ncli_status, automatic_repair):
        mon_type = RepairSkaledMonitor
    elif is_recreate_mode(check_status, schain_record):
        mon_type = RecreateSkaledMonitor
    elif is_new_node_mode(schain_record, action_manager.finish_ts):
        mon_type = NewNodeSkaledMonitor
    elif is_config_update_time(check_status, skaled_status):
        mon_type = UpdateConfigSkaledMonitor
    elif is_reload_group_mode(check_status, action_manager.upstream_finish_ts):
        mon_type = ReloadGroupSkaledMonitor
    elif is_reload_ip_mode(check_status, action_manager.econfig.reload_ts):
        mon_type = ReloadIpSkaledMonitor
    return mon_type
