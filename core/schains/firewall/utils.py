from typing import List

from .firewall_manager import SChainFirewallManager
from .entities import IpRange, PORTS_PER_SCHAIN
from .iptables import IptablesManager
from .rule_controller import SChainRuleController


def get_default_rule_controller(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: List[IpRange]
) -> SChainRuleController:
    im = IptablesManager()
    fm = SChainFirewallManager(
        name,
        base_port,
        base_port + PORTS_PER_SCHAIN,
        im
    )
    return SChainRuleController(
        fm,
        base_port,
        own_ip,
        node_ips,
        sync_ip_ranges=sync_agent_ranges
    )


def is_rules_synced(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: List[IpRange]
):
    rc = get_default_rule_controller(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_agent_ranges
    )
    return rc.is_rules_synced()


def sync_rules(
    name: str,
    base_port: int,
    own_ip: str,
    node_ips: List[str],
    sync_agent_ranges: List[IpRange]
):
    rc = get_default_rule_controller(
        name,
        base_port,
        own_ip,
        node_ips,
        sync_agent_ranges
    )
    return rc.sync_rules()
