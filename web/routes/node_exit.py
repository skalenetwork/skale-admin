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

from flask import Blueprint, request
from tools.custom_thread import CustomThread
from web.helper import construct_ok_response, login_required

logger = logging.getLogger(__name__)


def construct_node_exit_bp(node):
    node_exit_bp = Blueprint('node_exit', __name__)

    @node_exit_bp.route('/api/exit/start', method=['POST'])
    @login_required
    def node_exit_start():
        exit_thread = CustomThread('Start node exit', node.exit, once=True)
        exit_thread.start()

    @node_exit_bp.route('/api/exit/status', methods=['GET'])
    @login_required
    def node_exit_status():
        exit_status_data = node.exit_status()
        construct_ok_response(exit_status_data)

    @node_exit_bp.route('/api/exit/finalize', method=['POST'])
    @login_required
    def node_exit_finalize():
        pass
