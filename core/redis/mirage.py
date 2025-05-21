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

from typing import cast
from redis_om import get_redis_connection, HashModel, Field, Migrator
from skale.types.node import NodeId


class MirageNode(HashModel, index=True):
    id: int = Field(index=True)
    dkg_status: int

    class Meta:
        redis_client = get_redis_connection()


def add_or_get(node_id: NodeId, dkg_status: int) -> MirageNode:
    node = node_by_id(node_id)
    if node:
        return node
    else:
        new_node = MirageNode(id=node_id, dkg_status=dkg_status)
        new_node.save()
        return new_node


def node_by_id(node_id: NodeId) -> MirageNode | None:
    nodes = MirageNode.find(MirageNode.id == node_id).all()
    if len(nodes) == 0:
        return None
    return cast(MirageNode, nodes[0])


Migrator().run()

node = add_or_get(NodeId(1), 0)
print(node.dkg_status)
