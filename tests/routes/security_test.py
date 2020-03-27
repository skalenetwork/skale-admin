import pytest
import mock
import json

from flask import Flask
from tests.utils import get_bp_data, post_bp_data

from tools.docker_utils import DockerUtils
from web.routes.security import construct_security_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_security_bp(dutils))
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


@mock.patch('web.routes.security.crypto.load_certificate', new=load_certificate_mock)
def test_status(skale_bp):
    data = get_bp_data(skale_bp, '/api/ssl/status')
    assert data['expiration_date'] == '2020-01-01T00:00:00'
    assert data['status'] == 1
    assert data['issued_to'] == 1


@mock.patch('web.routes.security.request', new=RequestMock())
def test_upload(skale_bp):
    data = post_bp_data(skale_bp, '/api/ssl/upload', full_response=True)
    assert data['res'] == 1
