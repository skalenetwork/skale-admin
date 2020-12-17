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
from web.helper import construct_ok_response, construct_err_response, get_api_url
from tools.configs import SSL_CERTIFICATES_FILEPATH

logger = logging.getLogger(__name__)

CERTS_UPLOADED_ERR_MSG = 'SSL Certificates are already uploaded'
NO_REQUIRED_FILES_ERR_MSG = 'No required files added'
CERTS_HAS_INVALID_FORMAT = 'Certificates have invalid format'

SSL_KEY_NAME = 'ssl_key'
SSL_CRT_NAME = 'ssl_cert'

BLUEPRINT_NAME = 'ssl'


def construct_ssl_bp(docker_utils):
    ssl_bp = Blueprint(BLUEPRINT_NAME, __name__)

    @ssl_bp.route(get_api_url(BLUEPRINT_NAME, 'status'), methods=['GET'])
    def status():
        logger.debug(request)
        if is_ssl_folder_empty():
            return construct_ok_response(data={'is_empty': True})

        cert_filepath = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
        with open(cert_filepath) as cert_file:
            try:
                cert = crypto.load_certificate(
                    crypto.FILETYPE_PEM, cert_file.read())

                subject = cert.get_subject()
                issued_to = subject.CN
                expiration_date_raw = cert.get_notAfter()
                expiration_date = parser.parse(
                    expiration_date_raw).strftime('%Y-%m-%dT%H:%M:%S')
            except Exception:
                logger.exception('Error during parsing certs. May be they are invalid')
                return construct_err_response(msg=CERTS_HAS_INVALID_FORMAT)

            return construct_ok_response(data={
                'issued_to': issued_to,
                'expiration_date': expiration_date,
                'status': 1
            })

    @ssl_bp.route(get_api_url(BLUEPRINT_NAME, 'upload'), methods=['POST'])
    def upload():
        request_json = json.loads(request.form['json'])
        force = request_json.get('force') is True

        if not is_ssl_folder_empty() and not force:
            return construct_err_response(msg=CERTS_UPLOADED_ERR_MSG)
        if SSL_KEY_NAME not in request.files or SSL_CRT_NAME not in request.files:
            return construct_err_response(msg=NO_REQUIRED_FILES_ERR_MSG)

        ssl_key = request.files[SSL_KEY_NAME]
        ssl_cert = request.files[SSL_CRT_NAME]
        ssl_key.save(os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_KEY_NAME))
        ssl_cert.save(os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_CRT_NAME))

        docker_utils.restart_all_schains()

        return construct_ok_response()

    return ssl_bp
