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

# TODO: move rotation-related methods here


def get_rotation_state(skale, schain_name, node_id):
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    rotation_in_progress = skale.node_rotation.is_rotation_in_progress(schain_name)
    finish_ts = rotation_data['finish_ts']
    rotation_id = rotation_data['rotation_id']
    new_schain = rotation_data['new_node'] == node_id
    exiting_node = rotation_data['leaving_node'] == node_id
    return {
        'in_progress': rotation_in_progress,
        'new_schain': new_schain,
        'exiting_node': exiting_node,
        'finish_ts': finish_ts,
        'rotation_id': rotation_id
    }
