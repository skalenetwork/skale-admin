import filecmp
import json
import os
import pathlib
import time
from contextlib import contextmanager
from datetime import datetime

import mock

import pytest
from flask import Flask, appcontext_pushed, g

from tests.utils import generate_cert, get_bp_data
from tools.configs import CONFIG_FOLDER, SSL_CERTIFICATES_FILEPATH
from tools.docker_utils import DockerUtils
from web.routes.ssl import construct_ssl_bp
from web.helper import get_api_url


BLUEPRINT_NAME = 'ssl'


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_ssl_bp())

    def handler(sender, **kwargs):
        g.docker_utils = DockerUtils()

    with appcontext_pushed.connected_to(handler, app):
        yield app.test_client()


@pytest.fixture
def bad_cert(cert_key_pair):
    cert, key = cert_key_pair
    with open(cert, 'w') as cert_file:
        cert_file.write('WRONG CERT')
    yield cert, key


@pytest.fixture
def cert_key_pair_host():
    """ Creates cert-key pair in directory """
    """ that is not used for storing uploaded ssl certificates """
    cert_path = os.path.join(CONFIG_FOLDER, 'temp_ssl_cert')
    key_path = os.path.join(CONFIG_FOLDER, 'temp_ssl_key')
    generate_cert(cert_path, key_path)
    yield cert_path, key_path
    pathlib.Path(cert_path).unlink(missing_ok=True)
    pathlib.Path(key_path).unlink(missing_ok=True)
    # Ensure uploaded certs are removed
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    pathlib.Path(cert_path).unlink(missing_ok=True)
    pathlib.Path(key_path).unlink(missing_ok=True)


@pytest.fixture
def bad_cert_host(cert_key_pair_host):
    cert, key = cert_key_pair_host
    with open(cert, 'w') as cert_file:
        cert_file.write('WRONG CERT')
    yield cert, key


def test_status(skale_bp, cert_key_pair):
    year = int(datetime.utcfromtimestamp(time.time()).strftime('%Y'))
    month = datetime.utcfromtimestamp(time.time()).strftime('%m')
    day = datetime.utcfromtimestamp(time.time()).strftime('%d')
    year += 1
    expire_day_line = f'{year}-{month}-{day}'
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'status'))
    assert data['status'] == 'ok'
    assert data['payload']['issued_to'] is None
    assert data['payload']['expiration_date'].startswith(expire_day_line)


def test_status_bad_cert(skale_bp, bad_cert):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'status'))
    assert data['status'] == 'error'
    assert data['payload'] == 'Certificates have invalid format'


@contextmanager
def files_data(cert_path, key_path, force=False):
    with open(key_path, 'rb') as key_file, open(cert_path, 'rb') as cert_file:
        data = {
            'ssl_key': (
                key_file, os.path.basename(key_path),
                'application/octet-stream'),
            'ssl_cert': (
                cert_file, os.path.basename(cert_path),
                'application/octet-stream'),
            'json': json.dumps({'force': force})
        }
        yield data


def post_bp_files_data(bp, request, file_data, full_response=False, **kwargs):
    data = bp.post(request, data=file_data).data
    if full_response:
        return data
    return json.loads(data.decode('utf-8'))


def test_upload(skale_bp, ssl_folder, db, cert_key_pair_host):
    cert_path, key_path = cert_key_pair_host
    with mock.patch('web.routes.ssl.set_schains_need_reload'), \
            mock.patch('core.nginx.restart_nginx_container'):
        with files_data(cert_path, key_path, force=False) as data:
            response = post_bp_files_data(
                skale_bp,
                get_api_url(BLUEPRINT_NAME, 'upload'),
                file_data=data
            )
    assert response == {'status': 'ok', 'payload': {}}
    uploaded_cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
    uploaded_key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    assert filecmp.cmp(cert_path, uploaded_cert_path)
    assert filecmp.cmp(key_path, uploaded_key_path)


def test_upload_bad_cert(skale_bp, db, ssl_folder, bad_cert_host):
    cert_path, key_path = bad_cert_host
    with mock.patch('web.routes.ssl.set_schains_need_reload'), \
            mock.patch('core.nginx.restart_nginx_container'):
        with files_data(cert_path, key_path, force=False) as data:
            response = post_bp_files_data(
                skale_bp,
                get_api_url(BLUEPRINT_NAME, 'upload'),
                file_data=data
            )
            assert response == {
                'status': 'error',
                'payload': 'Certificates have invalid format'
            }


def test_upload_cert_exist(skale_bp, db, cert_key_pair_host, cert_key_pair):
    cert_path, key_path = cert_key_pair_host
    with mock.patch('web.routes.ssl.set_schains_need_reload'), \
            mock.patch('core.nginx.restart_nginx_container'):
        with files_data(cert_path, key_path, force=False) as data:
            response = post_bp_files_data(
                skale_bp,
                get_api_url(BLUEPRINT_NAME, 'upload'),
                file_data=data
            )
            assert response == {
                'status': 'error',
                'payload': 'SSL Certificates are already uploaded'
            }

        with files_data(cert_path, key_path, force=True) as data:
            response = post_bp_files_data(
                skale_bp,
                get_api_url(BLUEPRINT_NAME, 'upload'),
                file_data=data
            )
            assert response == {
                'status': 'ok',
                'payload': {}
            }
