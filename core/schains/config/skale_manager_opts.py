#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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

from dataclasses import dataclass

from skale import Skale


@dataclass
class SkaleManagerOpts:
    """Dataclass that represents skale-manager key of the skaleConfig section"""
    schains_internal_address: str
    nodes_address: str

    def to_dict(self):
        """Returns camel-case representation of the SkaleManagerOpts object"""
        return {
            'SchainsInternal': self.schains_internal_address,
            'Nodes': self.nodes_address
        }


def init_skale_manager_opts(skale: Skale) -> SkaleManagerOpts:
    return SkaleManagerOpts(
        schains_internal_address=skale.schains_internal.address,
        nodes_address=skale.nodes.address
    )
