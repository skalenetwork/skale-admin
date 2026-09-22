"""Authentication for endpoints reserved for the local node operator."""

import os
import re
import secrets
import stat
from collections.abc import Callable
from http import HTTPStatus
from typing import TypeVar

from flask import Flask, Response, current_app, jsonify, request

from tools.constants import SKALE_VOLUME_PATH

ADMIN_API_TOKEN_PATH = SKALE_VOLUME_PATH / 'auth' / 'admin-api.token'
F = TypeVar('F', bound=Callable)


def cli_only(view: F) -> F:
    """Mark a view for authentication before application resources are initialized."""
    view.cli_only = True  # type: ignore[attr-defined]
    return view


def init_cli_auth(app: Flask) -> None:
    # Register before the resource initialization hook in both API applications.
    app.before_request(authenticate_cli)


def authenticate_cli() -> Response | None:
    view = current_app.view_functions.get(request.endpoint or '')
    if not getattr(view, 'cli_only', False):
        return None

    try:
        fd = os.open(ADMIN_API_TOKEN_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'r', encoding='ascii') as token_file:
            info = os.fstat(token_file.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Invalid token file permissions')
            expected = token_file.read(66).removesuffix('\n')
        if not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('Invalid token file contents')
    except (OSError, ValueError):
        response = jsonify(
            status='error',
            payload='CLI authentication is unavailable. Provision the token with node CLI '
            'before starting the API.',
        )
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return response

    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if (
        scheme.lower() != 'bearer'
        or not re.fullmatch(r'[0-9a-f]{64}', token)
        or not secrets.compare_digest(token, expected)
    ):
        response = jsonify(status='error', payload='A valid node CLI credential is required')
        response.status_code = HTTPStatus.UNAUTHORIZED
        response.headers['WWW-Authenticate'] = 'Bearer realm="node-cli"'
        return response
    return None
