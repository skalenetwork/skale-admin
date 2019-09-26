#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging

from flask import Blueprint, request

from web.user import User
from web.helper import construct_ok_response, construct_err_response

logger = logging.getLogger(__name__)


def construct_auth_bp(user_session, token):
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/user-info', methods=['GET'])
    def get_user_info():
        logger.debug(request)
        user_info = user_session.get_current_user_info()
        return construct_ok_response(user_info)

    @auth_bp.route('/join', methods=['POST'])
    def join():
        request_data = request.json
        if not request_data.get('username') or not request_data.get(
                'password') or not request_data.get(
            'token'):
            return construct_err_response(400, [{'msg': 'Wrong data provided'}])

        if request_data['token'] != token:  # todo: check token from file!
            return construct_err_response(400, [{'msg': 'Token not match'}])

        user, err = User.join(request_data['username'], request_data['password'], token)
        if user:
            user_session.auth(user)
            return construct_ok_response()
        else:
            return construct_err_response(400, [{'msg': str(err)}])

    @auth_bp.route('/login', methods=['GET', 'POST'])
    def login():
        request_data = request.json
        if request.method == 'POST' and request_data.get('username'):
            res, err = User.login(request_data['username'], request_data['password'], user_session)
            if err:
                return construct_err_response(400, [{'msg': str(err)}])
            return construct_ok_response()
        return construct_err_response(400, [{'msg': 'Wrong data provided'}])

    @auth_bp.route('/logout')
    def logout():
        user_session.clear_session()
        return construct_ok_response()

    @auth_bp.route('/test-host')
    def test_host():
        return construct_ok_response()

    return auth_bp
