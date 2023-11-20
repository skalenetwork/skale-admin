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


class DKGStatus(int, Enum):
    NOT_STARTED = 1
    IN_PROGRESS = 2
    DONE = 3
    FAILED = 4
    KEY_GENERATION_ERROR = 5

    def is_done(self) -> bool:
        return self == DKGStatus.DONE


class DKGStep(int, Enum):
    NOT_STARTED = 0
    CLIENT_INITED = 1
    BROADCAST_SENT = 2
    ALRIGHT_SENT = 3
    KEY_GENERATION_ERROR = 4
    COMPLETED = 5
