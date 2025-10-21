import os
from urllib.parse import urlparse

from tools.configs import NODE_DATA_PATH
from tools.exceptions import MissingEnvVariableError

SGX_SERVER_URL = os.environ.get('SGX_SERVER_URL')

PARSED_SGX_URL = urlparse(SGX_SERVER_URL)
SGX_HTTPS_ENABLED = PARSED_SGX_URL.scheme == 'https'

SGX_CERTIFICATES_FOLDER_NAME = os.getenv('SGX_CERTIFICATES_DIR_NAME')
SGX_SSL_KEY_NAME = 'sgx.key'
SGX_SSL_CERT_NAME = 'sgx.crt'

SGX_CERTIFICATES_FOLDER = None
if SGX_CERTIFICATES_FOLDER_NAME:
    SGX_CERTIFICATES_FOLDER = os.path.join(NODE_DATA_PATH, SGX_CERTIFICATES_FOLDER_NAME)
else:
    SGX_CERTIFICATES_FOLDER = os.getenv('SGX_CERTIFICATES_FOLDER')

SGX_SSL_KEY_FILEPATH = None
SGX_SSL_CERT_FILEPATH = None
if SGX_HTTPS_ENABLED and SGX_CERTIFICATES_FOLDER:
    SGX_SSL_KEY_FILEPATH = os.path.join(SGX_CERTIFICATES_FOLDER, SGX_SSL_KEY_NAME)
    SGX_SSL_CERT_FILEPATH = os.path.join(SGX_CERTIFICATES_FOLDER, SGX_SSL_CERT_NAME)


def sgx_server_url() -> str:
    if not SGX_SERVER_URL:
        raise MissingEnvVariableError('SGX_SERVER_URL is not set.')
    return SGX_SERVER_URL


def sgx_ssl_key_filepath() -> str:
    if not SGX_SSL_KEY_FILEPATH:
        raise MissingEnvVariableError('SGX_SSL_KEY_FILEPATH is not set.')
    return SGX_SSL_KEY_FILEPATH


def sgx_ssl_cert_filepath() -> str:
    if not SGX_SSL_CERT_FILEPATH:
        raise MissingEnvVariableError('SGX_SSL_CERT_FILEPATH is not set.')
    return SGX_SSL_CERT_FILEPATH
