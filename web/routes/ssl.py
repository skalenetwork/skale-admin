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

from core.nginx import reload_nginx
from core.schains.ssl import is_ssl_folder_empty
from web.models.schain import set_schains_need_reload
from web.helper import construct_ok_response, construct_err_response, get_api_url
from tools.configs import SSL_CERTIFICATES_FILEPATH

logger = logging.getLogger(__name__)

CERTS_UPLOADED_ERR_MSG = 'SSL Certificates are already uploaded'
NO_REQUIRED_FILES_ERR_MSG = 'No required files added'
CERTS_HAS_INVALID_FORMAT = 'Certificates have invalid format'

SSL_KEY_NAME = 'ssl_key'
SSL_CRT_NAME = 'ssl_cert'

BLUEPRINT_NAME = 'ssl'


def cert_from_file(cert_filepath):
    if not os.path.isfile(cert_filepath):
        return None
    with open(cert_filepath) as cert_file:
        return cert_file.read()


def save_cert_key_pair(cert, key):
    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_KEY_NAME)
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, SSL_CRT_NAME)
    with open(cert_path, 'wb') as cert_file:
        cert_file.write(cert)
    with open(key_path, 'wb') as key_file:
        key_file.write(key)


def get_cert_info(cert):
    try:
        crypto_cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
        subject = crypto_cert.get_subject()
        issued_to = subject.CN
        expiration_date_raw = crypto_cert.get_notAfter()
        expiration_date = parser.parse(
            expiration_date_raw
        ).strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as err:
        logger.exception('Error during parsing certs')
        return 'error', {'msg': err}
    return 'ok', {
        'subject': subject,
        'issued_to': issued_to,
        'expiration_date': expiration_date
    }


def construct_ssl_bp():
    ssl_bp = Blueprint(BLUEPRINT_NAME, __name__)

    @ssl_bp.route(get_api_url(BLUEPRINT_NAME, 'status'), methods=['GET'])
    def status():
        logger.debug(request)
        if is_ssl_folder_empty():
            return construct_ok_response(data={'is_empty': True})

        cert_filepath = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
        cert = cert_from_file(cert_filepath)
        status, info = get_cert_info(cert)
        if status == 'error':
            return construct_err_response(msg=CERTS_HAS_INVALID_FORMAT)
        else:
            return construct_ok_response(data={
                'issued_to': info['issued_to'],
                'expiration_date': info['expiration_date']
            })

    @ssl_bp.route(get_api_url(BLUEPRINT_NAME, 'upload'), methods=['POST'])
    def upload():
        request_json = json.loads(request.form['json'])
        force = request_json.get('force') is True
        if not is_ssl_folder_empty() and not force:
            return construct_err_response(msg=CERTS_UPLOADED_ERR_MSG)
        if SSL_KEY_NAME not in request.files or \
                SSL_CRT_NAME not in request.files:
            return construct_err_response(msg=NO_REQUIRED_FILES_ERR_MSG)

        key = request.files[SSL_KEY_NAME].read()
        cert = request.files[SSL_CRT_NAME].read()

        status, info = get_cert_info(cert)
        if status == 'error':
            return construct_err_response(msg=CERTS_HAS_INVALID_FORMAT)

        save_cert_key_pair(cert, key)
        set_schains_need_reload()
        reload_nginx()
        return construct_ok_response()

    return ssl_bp
