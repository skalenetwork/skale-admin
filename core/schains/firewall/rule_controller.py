import itertools
from abc import ABC, abstractmethod
from typing import Generator, Iterable, List, Optional

from skale.sync_manager import IpRange  # type: ignore

from core.schains.firewall.entities import SChainRule, SkaledPorts


class IFirewallManager(ABC):
    @property
    @abstractmethod
    def rules(self) -> Iterable[SChainRule]:
        pass

    @abstractmethod
    def update_rules(self, rules: Iterable[SChainRule]) -> None:
        pass


class SChainRuleController:
    def __init__(
        self,
        firewall_manager: IFirewallManager,
        base_port: int,
        own_ip: str,
        node_ips: List[str],
        port_allocation: SkaledPorts,
        sync_ip_ranges: Optional[List[IpRange]] = None
    ):
        self.base_port = base_port
        self.own_ip = own_ip
        self.node_ips = node_ips
        self.sync_ip_ranges = sync_ip_ranges
        self.port_allocation = port_allocation
        self.firewall_manager = firewall_manager

    @property
    def internal_ports(self) -> Generator[int, None, None]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.CATCHUP,
                self.port_allocation.PROPOSAL,
                self.port_allocation.BINARY_CONSENSUS,
                self.port_allocation.ZMQ_BROADCAST
            )
        )

    @property
    def internal_rules(self) -> Iterable[SChainRule]:
        return (
            SChainRule(port, ip)
            for ip, port in zip(self.node_ips, self.internal_rules)
            if ip != self.own_ip
        )

    @property
    def public_ports(self) -> Iterable[SChainRule]:
        return (
            self.base_port + offset.value
            for offset in (
                self.port_allocation.HTTP_JSON,
                self.port_allocation.HTTPS_JSON,
                self.port_allocation.WS_JSON,
                self.port_allocation.WSS_JSON,
                self.port_allocation.INFO_HTTP_JSON,
                self.port_allocation.PG_HTTP_RPC_JSON,
                self.port_allocation.PG_HTTPS_RPC_JSON,
                self.port_allocation.PG_INFO_HTTP_RPC_JSON,
                self.port_allocation.PG_INFO_HTTPS_RPC_JSON,
            )
        )

    @property
    def public_rules(self) -> Iterable[SChainRule]:
        return (SChainRule(port) for port in self.internal_rules)

    @property
    def sync_agent_port(self) -> int:
        return self.base_port + self.port_allocation.CATCHUP

    @property
    def sync_agent_rules(self) -> Iterable[SChainRule]:
        if not self.sync_ip_ranges:
            raise StopIteration
        return (
            SChainRule(self.sync_agent_port, r.start_ip, r.end_ip)
            for r in self.sync_ip_ranges
        )

    @property
    def rules(self) -> Iterable[SChainRule]:
        return itertools.chain.from_iterable((
            self.internal_rules,
            self.public_rules,
            self.sync_agent_rules
        ))

    def get_rules(self) -> List[SChainRule]:
        return list(self.rules)

    def is_rules_synced(self) -> bool:
        return set(self.rules) == set(self.firewall_manager.rules)

    def sync_rules(self) -> None:
        self.firewall_manager.update_rules(self.rules)
