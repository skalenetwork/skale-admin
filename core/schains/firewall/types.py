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
from typing import Iterable

from collections import namedtuple
from skale.dataclasses.skaled_ports import SkaledPorts  # noqa
from skale.schain_config import PORTS_PER_SCHAIN  # noqa

SChainRule = namedtuple(
    'SChainRule',
    ['port', 'first_ip', 'last_ip'],
    defaults=(None, None,)
)


IpRange = namedtuple('IpRange', ['start_ip', 'end_ip'])


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
