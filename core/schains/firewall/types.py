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

from abc import ABC, abstractmethod
from functools import total_ordering
from typing import Iterable, Optional

from collections import namedtuple
from skale.dataclasses.skaled_ports import SkaledPorts  # noqa
from skale.schain_config import PORTS_PER_SCHAIN  # noqa


@total_ordering
class SChainRule(namedtuple('SChainRule', ['port', 'first_ip', 'last_ip'])):
    def __new__(
        cls,
        port: int,
        first_ip: Optional[str] = None,
        last_ip: Optional[str] = None
    ) -> 'SChainRule':
        if first_ip and not last_ip:
            last_ip = first_ip
        return super(SChainRule, cls).__new__(cls, port, first_ip, last_ip)

    def __repr__(self) -> str:
        if not self.first_ip:
            return f'SChainRule(:{self.port})'
        else:
            return f'SChainRule({self.first_ip}:{self.port}-{self.last_ip}:{self.port})'  # noqa

    def __hash__(self) -> int:
        return hash(tuple(self))

    def __eq__(self, other) -> bool:
        return self.port == other.port and \
                self.first_ip == other.first_ip and \
                self.last_ip == other.last_ip

    def __lt__(self, other) -> bool:
        if self.port != other.port:
            return self.port < other.port
        elif self.first_ip != other.first_ip:
            ip_a = '' if self.first_ip is None else self.first_ip
            ip_b = '' if other.first_ip is None else other.first_ip
            return ip_a < ip_b
        elif self.last_ip != other.last_ip:
            ip_a = '' if self.last_ip is None else self.last_ip
            ip_b = '' if other.last_ip is None else other.last_ip
            return ip_a < ip_b
        else:  # pragma: no cover
            return True


IpRange = namedtuple('IpRange', ['start_ip', 'end_ip'])


class IHostFirewallController(ABC):
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

    @abstractmethod
    def flush(self) -> None:  # pragma: no cover  # noqa
        pass


class IRuleController(ABC):
    @abstractmethod
    def is_rules_synced(self) -> bool:  # pragma: no cover
        pass

    @abstractmethod
    def sync(self) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def cleanup(self) -> None:  # pragma: no cover
        pass
