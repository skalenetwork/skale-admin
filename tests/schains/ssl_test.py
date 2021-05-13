import os

from tools.configs import NODE_DATA_PATH
from core.schains.ssl import get_ssl_filepath


def test_get_ssl_filepath(cert_key_pair):
    ssl_key_path, ssl_cert_path = get_ssl_filepath()

    certs_filepath = os.path.join(NODE_DATA_PATH, 'ssl')

    assert ssl_key_path == os.path.join(certs_filepath, 'ssl_key')
    assert ssl_cert_path == os.path.join(certs_filepath, 'ssl_cert')
