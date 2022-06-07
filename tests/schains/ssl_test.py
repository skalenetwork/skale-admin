import os
from datetime import datetime

from tools.configs import NODE_DATA_PATH
from core.schains.ssl import get_ssl_filepath, get_ssl_files_change_date


def test_get_ssl_filepath(cert_key_pair):
    ssl_key_path, ssl_cert_path = get_ssl_filepath()

    certs_filepath = os.path.join(NODE_DATA_PATH, 'ssl')

    assert ssl_key_path == os.path.join(certs_filepath, 'ssl_key')
    assert ssl_cert_path == os.path.join(certs_filepath, 'ssl_cert')


def test_get_ssl_files_change_date(cert_key_pair):
    time_now = datetime.now()
    change_date = get_ssl_files_change_date()

    assert time_now > change_date
    assert time_now.timestamp() - 1000 < change_date.timestamp()
