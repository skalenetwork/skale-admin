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

import logging
from typing import Type

from core.firewall.utils import get_mirage_network_scope_rule_controller
from core.monitor.monitor_base import BaseSkaledMonitor
from core.node_config import NodeConfig
from core.checks.mirage import SkaledChecks
from core.checks.base import get_api_checks_status, TG_ALLOWED_CHECKS
from core.config.schain.file_manager import ConfigFileManager
from core.redis.chain_record import ChainRecord
from core.firewall import get_default_rule_controller

from core.monitor.mirage.action_skaled import MirageSkaledActionManager

from core.chain.status import SkaledStatus, get_skaled_status

from core.types.chain import MirageChainName
from tools.docker_utils import DockerUtils
from tools.configs import SYNC_NODE
from tools.notifications.messages import notify_checks
from tools.helper import no_hyphens
from tools.resources import get_statsd_client

logger = logging.getLogger(__name__)


def run_skaled_pipeline(
    chain_name: MirageChainName,
    node_config: NodeConfig,
    dutils: DockerUtils | None = None,
) -> None:
    logger.info('Initializing chain record')
    chain_record = ChainRecord(name=chain_name)
    if not chain_record:
        raise ValueError(f'Chain record for {chain_name} not found')
    logger.info('Record: %s', chain_record.to_dict())

    dutils = dutils or DockerUtils()

    config_file_manager = ConfigFileManager(chain_name=chain_name)
    conf = config_file_manager.latest_upstream_config if upstream else self.cfm.skaled_config
    rc = get_mirage_committee_scope_rule_controller(
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips
    )
    logger.info('Initializing skaled checks')
    skaled_checks = SkaledChecks(
        chain_name=chain_name,
        chain_record=chain_record,
        rule_controller=None,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )

    logger.info('Initializing skaled status')
    skaled_status = get_skaled_status(chain_name)

    logger.info('Initializing skaled action manager')
    skaled_am = MirageSkaledActionManager(
        chain_name=chain_name,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        dutils=dutils,
    )

    logger.info('Gathering skaled status')
    check_status = skaled_checks.get_all(log=False, expose=True)

    logger.info('Get automatic repair option')
    logger.info('Creating api only check results')
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(chain_name, node_config.all(), api_status)

    logger.info('Skaled check status: %s', check_status)

    logger.info('Upstream config %s', skaled_am.upstream_config_path)

    mon = get_skaled_monitor(
        action_manager=skaled_am,
        check_status=check_status,
        chain_record=chain_record,
        skaled_status=skaled_status,
    )

    statsd_client = get_statsd_client()
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(chain_name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(chain_name)}'):
        mon(skaled_am, skaled_checks).run()


def get_skaled_monitor(
    action_manager: MirageSkaledActionManager,
    check_status: dict,
    chain_record: ChainRecord,
    skaled_status: SkaledStatus | None,
) -> Type[BaseSkaledMonitor]:
    logger.info('Choosing skaled monitor')
    if skaled_status:
        skaled_status.log()

    mon_type: Type[BaseSkaledMonitor] = RegularSkaledMonitor

    if SYNC_NODE:
        # todod: implement sync node monitors
        return mon_type

    # todod: implement regualr node monitors

    # if not check_status['config']:
    #     mon_type = NoConfigSkaledMonitor
    # elif is_backup_mode(schain_record):
    #     mon_type = BackupSkaledMonitor
    # elif is_repair_mode(schain_record, check_status, skaled_status, ncli_status, automatic_repair): # noqa: E501
    #     mon_type = RepairSkaledMonitor
    # elif is_recreate_mode(check_status, schain_record):
    #     mon_type = RecreateSkaledMonitor
    # elif is_new_node_mode(schain_record, action_manager.finish_ts):
    #     mon_type = NewNodeSkaledMonitor
    # elif is_config_update_time(check_status, skaled_status):
    #     mon_type = UpdateConfigSkaledMonitor
    # elif is_reload_group_mode(check_status, action_manager.upstream_finish_ts):
    #     mon_type = ReloadGroupSkaledMonitor
    # elif is_reload_ip_mode(check_status, action_manager.econfig.reload_ts):
    #     mon_type = ReloadIpSkaledMonitor
    return mon_type


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
