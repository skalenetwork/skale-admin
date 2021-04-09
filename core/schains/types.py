#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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

from enum import Enum


class SchainType(Enum):
    test = 0
    test4 = 32
    large = 128
    medium = 4
    small = 1


class ContainerType(Enum):
    base = 0
    schain = 1
    ima = 2


class MetricType(Enum):
    cpu_shares = 0
    mem = 1
    disk = 2
    volume_limits = 3
    storage_limit = 4
