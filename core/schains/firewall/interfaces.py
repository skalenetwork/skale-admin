from abc import ABC, abstractmethod
from typing import Iterable
from core.schains.firewall.entities import SChainRule


class IHostFirewallManager(ABC):
    @abstractmethod
    def add_rule(self, rule: SChainRule) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def remove_rule(self, rule: SChainRule) -> None:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def rules(self) -> Iterable[SChainRule]:  # pragma: no cover
        pass

    @abstractmethod
    def has_rule(self, rule: SChainRule) -> bool:  # pragma: no cover
        pass


class IFirewallManager(ABC):
    @property
    @abstractmethod
    def rules(self) -> Iterable[SChainRule]:  # pragma: no cover
        pass

    @abstractmethod
    def update_rules(self, rules: Iterable[SChainRule]) -> None:  # pragma: no cover  # noqa
        pass


class IRuleController(ABC):
    @abstractmethod
    def is_rules_synced(self) -> bool:  # pragma: no cover
        pass

    @abstractmethod
    def sync_rules(self) -> None:  # pragma: no cover
        pass
