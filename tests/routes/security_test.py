import pytest
import mock
import json

from flask import Flask, appcontext_pushed, g
from tests.utils import get_bp_data, post_bp_data

from tools.docker_utils import DockerUtils
from web.routes.security import construct_security_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_security_bp())

    def handler(sender, **kwargs):
        g.docker_utils = DockerUtils()

    with appcontext_pushed.connected_to(handler, app):
        yield app.test_client()


def load_certificate_mock(type, buffer):
    class CertificateMock:
        @staticmethod
        def get_subject():
            class SubjectMock:
                def __init__(self):
                    self.CN = 1

            return SubjectMock()

        @staticmethod
        def get_notAfter():
            return '2020-01-01 00:00:00'

    return CertificateMock


class RequestMock:
    def __init__(self):
        class FileMock:
            @staticmethod
            def save(path):
                pass

        self.form = {'json': json.dumps({'force': True})}
        file = FileMock()
        self.files = {'ssl_key': file, 'ssl_cert': file}


@mock.patch('web.routes.security.crypto.load_certificate',
            new=load_certificate_mock)
def test_status(skale_bp):
    data = get_bp_data(skale_bp, '/api/ssl/status')
    assert data == {
        'status': 'ok',
        'payload': {
            'expiration_date': '2020-01-01T00:00:00',
            'issued_to': 1,
            'status': 1
        }
    }, data


@mock.patch('web.routes.security.request', new=RequestMock())
def test_upload(skale_bp):
    response = post_bp_data(skale_bp, '/api/ssl/upload', full_response=True)
    assert response == {'status': 'ok', 'payload': {}}
