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

import logging

from flask import Blueprint
from web.helper import login_required

logger = logging.getLogger(__name__)


def construct_node_exit_bp(skale):
    node_exit_bp = Blueprint('node_exit', __name__)

    @node_exit_bp.route('/api/exit/start')
    @login_required
    def node_exit_start():
        pass

    @node_exit_bp.route('/api/exit/status')
    @login_required
    def node_exit_status():
        pass

    @node_exit_bp.route('/api/exit/finalize')
    @login_required
    def node_exit_finalize():
        pass
