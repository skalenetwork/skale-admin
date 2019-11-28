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

import os
import logging
from http import HTTPStatus

from flask import Blueprint, request
from werkzeug.utils import secure_filename

from web.helper import construct_ok_response, construct_err_response, login_required
from tools.configs import SSL_CERTIFICATES_FILEPATH

logger = logging.getLogger(__name__)


def construct_security_bp():
    security_bp = Blueprint('security', __name__)

    @security_bp.route('/upload-certificate', methods=['POST', 'GET'])
    @login_required
    def upload_ssl_certificate():
        logger.debug(request)

        if request.method == 'POST':
            if 'name' not in request.form:
                return construct_err_response(HTTPStatus.BAD_REQUEST, ['Please provide name'])

            if 'sslKey' not in request.files or 'sslCert' not in request.files:
                return construct_err_response(HTTPStatus.BAD_REQUEST, ['No required files added'])

            ssl_key = request.files['sslKey']
            ssl_cert = request.files['sslCert']

            if ssl_key and ssl_cert:
                name = request.form['name']
                dir_name = secure_filename(name)
                cert_location_path = os.path.join(SSL_CERTIFICATES_FILEPATH, dir_name)

                if not os.path.exists(cert_location_path):
                    os.mkdir(cert_location_path)
                else:
                    return construct_err_response(HTTPStatus.BAD_REQUEST, ['Name is already taken'])

                ssl_key.save(os.path.join(cert_location_path, 'ssl_key'))
                ssl_cert.save(os.path.join(cert_location_path, 'ssl_cert'))

                return construct_ok_response(1)

    @security_bp.route('/certificates-info', methods=['GET'])
    @login_required
    def get_certificates_info():
        logger.debug(request)
        res = []
        ssl_dirs = os.listdir(SSL_CERTIFICATES_FILEPATH)

        if len(ssl_dirs) > 0:
            default_cert = ssl_dirs.pop(0)
            res.append({'name': default_cert, 'status': 'added'})

        for ssl_dir in ssl_dirs:
            res.append({'name': ssl_dir, 'status': 'inactive'})
        return construct_ok_response(res)

    return security_bp
