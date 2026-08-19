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

from functools import wraps

from skale import SkaleManager
from skale.types.schain import SchainName

from core.dkg.utils import SchainNotFoundError


def ensure_schain_exists(skale: SkaleManager, schain_name: SchainName) -> None:
    if not skale.schains_internal.is_schain_exist(schain_name):
        raise SchainNotFoundError(f'sChain {schain_name} does not exist in SKALE Manager')


def require_schain_exists(func):
    @wraps(func)
    def wrapper(instance, *args, **kwargs):
        ensure_schain_exists(instance.skale, instance.chain_name)
        return func(instance, *args, **kwargs)

    return wrapper
