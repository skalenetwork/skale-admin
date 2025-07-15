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

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import ClassVar

from skale.skale_base import SkaleBase

logger = logging.getLogger(__name__)


@dataclass
class DKGEvent:
    nodeIndex: str
    secretKeyContribution: str
    verificationVector: str


class BaseFilter(ABC):
    event_hash: ClassVar[str]
    skale: ClassVar[SkaleBase]

    def __init__(self, n):
        self.n = n
        self.t = (2 * n + 1) // 3

    @abstractmethod
    def check_event(self, receipt):
        """Check if the event is relevant to DKG filter."""
        pass

    @abstractmethod
    def parse_event(self, receipt):
        """Parse the event data from the receipt."""
        pass

    @abstractmethod
    def get_events(self, from_channel_started_block=False):
        """Get broadcast events from the blockchain."""
        pass
