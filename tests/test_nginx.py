import shutil
import os
from pathlib import Path

import pytest

from core.nginx import reload_nginx
from tools.configs import CONFIG_FOLDER, SSL_CERTIFICATES_FILEPATH
from tools.configs.nginx import NGINX_CONTAINER_NAME


TEMPLATE = """
limit_req_zone $binary_remote_addr zone=one:10m rate=7r/s;

server {
    listen 3009;

    {% if ssl %}
    listen 311 ssl;
    ssl_certificate     /ssl/ssl_cert;
    ssl_certificate_key /ssl/ssl_key;
    {% endif %}

    proxy_read_timeout 500s;
    proxy_connect_timeout 500s;
    proxy_send_timeout 500s;

    error_log /var/log/nginx/error.log warn;
    client_max_body_size 20m;

    server_name localhost;
    limit_req zone=one burst=10;

    location / {
        include uwsgi_params;
        uwsgi_read_timeout 500s;
        uwsgi_socket_keepalive on;
        uwsgi_pass 127.0.0.1:3010;
    }
}

server {
    listen 80;

    {% if ssl %}
    listen 443 ssl;
    ssl_certificate     /ssl/ssl_cert;
    ssl_certificate_key /ssl/ssl_key;
    {% endif %}

    error_log /var/log/nginx/error.log warn;
    client_max_body_size 20m;
    server_name localhost;
    limit_req zone=one burst=50;

    location / {
        root /filestorage;
    }
}
"""


@pytest.fixture
def tmp_dir():
    path = os.path.join(CONFIG_FOLDER, 'test')
    Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


@pytest.fixture
def template(tmp_dir):
    path = os.path.join(tmp_dir, 'nginx.conf.j2')
    with open(path, 'w') as temp:
        temp.write(TEMPLATE)
    return path


@pytest.fixture
def config_path(tmp_dir):
    path = os.path.join(tmp_dir, 'default.conf')
    return path


@pytest.fixture
def ssl_dir():
    path = SSL_CERTIFICATES_FILEPATH
    Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


@pytest.fixture
def nginx_container(tmp_dir, ssl_dir, config_path, dutils):
    try:
        c = dutils.run_container(
            'nginx:1.20.2',
            NGINX_CONTAINER_NAME,
            volumes={
                tmp_dir: {
                    'bind': '/etc/nginx/conf.d',
                    'mode': 'ro',
                    'propagation': 'slave'
                },
                ssl_dir: {
                    'bind': '/ssl',
                    'mode': 'ro',
                    'propagation': 'slave'
                }
            }
        )
        yield c
    finally:
        dutils.safe_rm(NGINX_CONTAINER_NAME)


def get_config(config_path):
    with open(config_path) as config_file:
        return config_file.read()


def test_nginx_reload(
    dutils,
    ssl_dir,
    tmp_dir,
    template,
    config_path,
    nginx_container
):
    reload_nginx(template, config_path, dutils=dutils)

    # Check that container is running
    info = dutils.get_info(NGINX_CONTAINER_NAME)
    state = info['stats']['State']
    assert state['Status'] == 'running'
    config = get_config(config_path)

    # Check that config is correct
    assert config == '\nlimit_req_zone $binary_remote_addr zone=one:10m rate=7r/s;\n\nserver {\n    listen 3009;\n\n    \n\n    proxy_read_timeout 500s;\n    proxy_connect_timeout 500s;\n    proxy_send_timeout 500s;\n\n    error_log /var/log/nginx/error.log warn;\n    client_max_body_size 20m;\n\n    server_name localhost;\n    limit_req zone=one burst=10;\n\n    location / {\n        include uwsgi_params;\n        uwsgi_read_timeout 500s;\n        uwsgi_socket_keepalive on;\n        uwsgi_pass 127.0.0.1:3010;\n    }\n}\n\nserver {\n    listen 80;\n\n    \n\n    error_log /var/log/nginx/error.log warn;\n    client_max_body_size 20m;\n    server_name localhost;\n    limit_req zone=one burst=50;\n\n    location / {\n        root /filestorage;\n    }\n}'   # noqa
    assert 'ssl' not in config

    # Creating fake certificates
    key_path = os.path.join(ssl_dir, 'ssl_key')
    chain_path = os.path.join(ssl_dir, 'ssl_cert')

    Path(key_path).touch()
    Path(chain_path).touch()

    reload_nginx(template, config_path, dutils=dutils)

    # Check that config is correct
    config = get_config(config_path)
    assert config == '\nlimit_req_zone $binary_remote_addr zone=one:10m rate=7r/s;\n\nserver {\n    listen 3009;\n\n    \n    listen 311 ssl;\n    ssl_certificate     /ssl/ssl_cert;\n    ssl_certificate_key /ssl/ssl_key;\n    \n\n    proxy_read_timeout 500s;\n    proxy_connect_timeout 500s;\n    proxy_send_timeout 500s;\n\n    error_log /var/log/nginx/error.log warn;\n    client_max_body_size 20m;\n\n    server_name localhost;\n    limit_req zone=one burst=10;\n\n    location / {\n        include uwsgi_params;\n        uwsgi_read_timeout 500s;\n        uwsgi_socket_keepalive on;\n        uwsgi_pass 127.0.0.1:3010;\n    }\n}\n\nserver {\n    listen 80;\n\n    \n    listen 443 ssl;\n    ssl_certificate     /ssl/ssl_cert;\n    ssl_certificate_key /ssl/ssl_key;\n    \n\n    error_log /var/log/nginx/error.log warn;\n    client_max_body_size 20m;\n    server_name localhost;\n    limit_req zone=one burst=50;\n\n    location / {\n        root /filestorage;\n    }\n}'  # noqa
    assert 'ssl' in config
