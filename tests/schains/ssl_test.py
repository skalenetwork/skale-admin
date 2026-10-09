import os
from datetime import datetime

from core.chain.ssl import get_ssl_filepath, get_ssl_files_change_date, is_ssl_on
from tools.constants import NODE_DATA_PATH


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


def test_ssl_is_off_without_certificates(ssl_folder):
    assert not is_ssl_on()
    assert get_ssl_filepath() == ('NULL', 'NULL')
    assert get_ssl_files_change_date() is None


def test_ssl_is_off_with_half_a_pair(cert_key_pair):
    _, key_path = cert_key_pair
    assert is_ssl_on()
    os.remove(key_path)
    # skaled exits when it is pointed at a key that is not there
    assert not is_ssl_on()
    assert get_ssl_filepath() == ('NULL', 'NULL')
    assert get_ssl_files_change_date() is None
