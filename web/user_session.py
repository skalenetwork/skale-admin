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

from web.user import User


class UserSession():
    def __init__(self, session):
        self.session = session

    def auth(self, user):
        self.session['logged_in'] = True
        self.session['user_id'] = user.id
        self.session['username'] = user.username

    def get_current_user(self):
        if self.session.get('logged_in'):
            try:
                return User.get(User.id == self.session['user_id'])
            except User.DoesNotExist:
                return None

    def clear_session(self):
        self.session.pop('logged_in', None)

    def get_current_user_info(self):
        current_user = self.get_current_user()

        if not current_user:
            self.clear_session()

        if not current_user:
            if User.check_no_users():
                return {'no_users': True}
            return None
        return {
            'username': current_user.username,
            'join_date': str(current_user.join_date)
        }
