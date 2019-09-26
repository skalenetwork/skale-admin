import os
from tools.config import SSL_CERTIFICATES_FILEPATH


def get_default_cert_location():
    ssl_dirs_dirs = os.listdir(SSL_CERTIFICATES_FILEPATH)
    if len(ssl_dirs_dirs) > 0:
        return os.path.join(SSL_CERTIFICATES_FILEPATH, ssl_dirs_dirs[0])


def get_ssl_filepath():
    cert_location_path = get_default_cert_location()
    if not cert_location_path or not os.path.exists(cert_location_path):
        return 'NULL', 'NULL'
    else:
        return os.path.join(cert_location_path, 'ssl_key'), os.path.join(cert_location_path,
                                                                         'ssl_cert')
