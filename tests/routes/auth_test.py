from functools import wraps

import pytest
from flask import Flask

from web import auth

TOKEN = 'ab' * 32


@pytest.fixture
def token_path(tmp_path, monkeypatch):
    path = tmp_path / 'auth' / 'admin-api.token'
    path.parent.mkdir(mode=0o700)
    path.write_text(TOKEN + '\n')
    path.chmod(0o600)
    monkeypatch.setattr(auth, 'ADMIN_API_TOKEN_PATH', path)
    return path


@pytest.fixture
def client(token_path):
    app = Flask(__name__)
    app.testing = True
    auth.init_cli_auth(app)
    calls = []

    @app.before_request
    def initialize_resources():
        calls.append('resources')

    def initialize_wallet(view):
        @wraps(view)
        def wrapper():
            calls.append('wallet')
            return view()

        return wrapper

    @app.route('/protected', methods=['GET', 'POST'])
    @auth.cli_only
    @initialize_wallet
    def protected():
        calls.append('operation')
        return {'status': 'ok', 'payload': {}}

    @app.route('/public', methods=['GET', 'POST'])
    def public():
        return {'status': 'ok', 'payload': {}}

    return app.test_client(), calls


@pytest.mark.parametrize('method', ['GET', 'HEAD', 'POST', 'OPTIONS'])
@pytest.mark.parametrize(
    'authorization', ['', 'Bearer ', 'Basic credentials', 'Bearer ' + 'cd' * 32, 'Bearer é']
)
def test_rejects_before_initialization(client, method, authorization):
    http, calls = client
    response = http.open('/protected', method=method, headers={'Authorization': authorization})
    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'] == 'Bearer realm="node-cli"'
    assert calls == []


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_accepts_valid_token(client, method):
    http, calls = client
    response = http.open('/protected', method=method, headers={'Authorization': f'Bearer {TOKEN}'})
    assert response.status_code == 200
    assert calls == ['resources', 'wallet', 'operation']


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_public_route_does_not_need_token(client, token_path, method):
    token_path.unlink()
    http, _ = client
    assert http.open('/public', method=method).status_code == 200
    assert http.get('/unknown').status_code == 404


@pytest.mark.parametrize(
    'bad_file', ['missing', 'empty', 'malformed', 'oversized', 'readable', 'symlink']
)
def test_fails_closed_on_invalid_server_credential(client, token_path, bad_file):
    if bad_file == 'missing':
        token_path.unlink()
    elif bad_file == 'readable':
        token_path.chmod(0o644)
    elif bad_file == 'symlink':
        target = token_path.with_suffix('.target')
        token_path.rename(target)
        token_path.symlink_to(target)
    else:
        token_path.write_text(
            {'empty': '', 'malformed': 'é', 'oversized': TOKEN + '\n\nmore'}[bad_file]
        )
    http, calls = client
    response = http.get('/protected', headers={'Authorization': f'Bearer {TOKEN}'})
    assert response.status_code == 503
    assert response.json['status'] == 'error'
    assert calls == []


def test_rotation_is_seen_without_restarting_workers(client, token_path):
    http, _ = client
    replacement = 'cd' * 32
    token_path.write_text(replacement + '\n')
    assert http.get('/protected', headers={'Authorization': f'Bearer {TOKEN}'}).status_code == 401
    assert (
        http.get('/protected', headers={'Authorization': f'Bearer {replacement}'}).status_code
        == 200
    )
