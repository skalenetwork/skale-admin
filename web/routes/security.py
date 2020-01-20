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
import json
import logging

from dateutil import parser
from OpenSSL import crypto

from flask import Blueprint, request

from core.schains.ssl import is_ssl_folder_empty
from web.helper import construct_ok_response, construct_bad_req_response, login_required
from tools.configs import SSL_CERTIFICATES_FILEPATH

logger = logging.getLogger(__name__)

CERTS_UPLOADED_ERR_MSG = 'SSL Certificates are already uploaded'
NO_REQUIRED_FILES_ERR_MSG = 'No required files added'

SSL_KEY_NAME = 'ssl_key'
SSL_CRT_NAME = 'ssl_cert'


def construct_security_bp():
    security_bp = Blueprint('security', __name__)

    @security_bp.route('/api/ssl/status', methods=['GET'])
    @login_required
    def status():
        logger.debug(request)
        if is_ssl_folder_empty():
            return construct_ok_response({'status': 0})

        cert_file = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_file).read())

        subject = cert.get_subject()
        issued_to = subject.CN
        expiration_date_raw = cert.get_notAfter()
        expiration_date = parser.parse(expiration_date_raw).strftime('%Y-%m-%dT%H:%M:%S')
        return construct_ok_response({
            'issued_to': issued_to,
            'expiration_date': expiration_date,
            'status': 1
        })

    @security_bp.route('/api/ssl/upload', methods=['POST'])
    @login_required
    def upload():
        request_json = json.loads(request.form['json'])
        force = request_json.get('force') is True

        if not is_ssl_folder_empty() and not force:
            return construct_bad_req_response(CERTS_UPLOADED_ERR_MSG)
        if SSL_KEY_NAME not in request.files or SSL_CRT_NAME not in request.files:
            return construct_bad_req_response(NO_REQUIRED_FILES_ERR_MSG)

        ssl_key = request.files[SSL_KEY_NAME]
        ssl_cert = request.files[SSL_CRT_NAME]
        ssl_key.save(os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_KEY_NAME))
        ssl_cert.save(os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_CRT_NAME))

        return construct_ok_response()

    return security_bp
