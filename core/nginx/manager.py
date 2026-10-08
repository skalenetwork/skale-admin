#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026-Present SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
import re
import time
from pathlib import Path
from typing import Callable

from filelock import FileLock, Timeout

from core.chain.ssl import is_ssl_on
from core.config.endpoint import get_local_chain_http_endpoint_from_config
from core.config.schain.file_manager import ConfigFileManager
from core.nginx.config import PROBE_PATH, render_base_config
from tools.constants import (
    NGINX_BASE_CONFIG_FILEPATH,
    NGINX_CHAINS_PATH,
    NGINX_CONTAINER_NAME,
    NGINX_LOCK_PATH,
)
from tools.docker_utils import DockerUtils
from tools.helper import is_fair

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 120
# nginx retries a busy listener port five times, 500 ms apart, before it keeps the old config
APPLY_TIMEOUT_SECONDS = 10
START_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 0.5

WATCHDOG_HTTP_PORT = 3009
# stub_status in base.conf, the compose healthcheck asks it too
STATUS_URL = f'http://127.0.0.1:{WATCHDOG_HTTP_PORT}/nginx-status'
# nginx binds all listeners of a new config or none, so one base.conf server speaks for all
BASE_PROBE_URL = f'http://127.0.0.1:{WATCHDOG_HTTP_PORT}{PROBE_PATH}'
BASE_HEADER = '# node base config, rendered by node-cli and skale-admin: fingerprint '

CHAIN_HEADER = re.compile(
    r'# sChain (?P<chain>\S+), rendered by skale-admin: '
    r'http (?P<port>\d+) fingerprint (?P<fingerprint>[0-9a-f]+)\n'
)


class NginxReloadError(Exception):
    pass


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


def _write(path: Path, text: str | None) -> None:
    """Atomic within the directory nginx has mounted, so it never reads a partial file"""
    if text is None:
        path.unlink(missing_ok=True)
        return
    tmp_path = path.with_name(f'.{path.name}.tmp')
    tmp_path.write_text(text)
    os.replace(tmp_path, path)


def wait_for(predicate: Callable[[], bool], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_INTERVAL_SECONDS)
    return True


def locked(lock_path: Path, action: Callable[[], bool]) -> bool:
    """Runs action under the lock that serialises nginx changes across chains"""
    try:
        with FileLock(lock_path, timeout=LOCK_TIMEOUT_SECONDS):
            return action()
    except Timeout:
        logger.error('Timed out waiting for %s', lock_path)
        return False


def chain_probe(text: str | None) -> tuple[str, str] | None:
    """URL and expected answer of the probe location of a rendered chain file"""
    match = CHAIN_HEADER.match(text or '')
    if match is None:
        return None
    url = f'http://127.0.0.1:{match["port"]}{PROBE_PATH}'
    return url, f'{match["chain"]} {match["fingerprint"]}'


class NginxContainer:
    name = NGINX_CONTAINER_NAME

    def __init__(self, dutils: DockerUtils | None = None) -> None:
        self.dutils = dutils or DockerUtils()

    def is_running(self) -> bool:
        return self.dutils.is_container_running(self.name)

    def _exec(self, cmd: list[str]) -> tuple[int, str]:
        result = self.dutils.client.containers.get(self.name).exec_run(cmd)
        return result.exit_code, result.output.decode(errors='replace')

    def is_ready(self) -> bool:
        return self.answers(STATUS_URL) is not None

    def ensure_running(self) -> bool:
        """Start nginx if it is down and wait for its master: a reload before that fails"""
        if not self.is_running():
            logger.warning('%s is not running, starting it', self.name)
            try:
                self.dutils.client.containers.get(self.name).restart()
            except Exception:
                logger.exception('Could not start %s', self.name)
                return False
        return wait_for(self.is_ready, START_TIMEOUT_SECONDS)

    def reload(self) -> None:
        """nginx -t and a graceful reload; exit 0 does not mean nginx took the new config"""
        code, output = self._exec(['nginx', '-t'])
        if code != 0:
            raise NginxReloadError(f'nginx config test failed: {output}')
        code, output = self._exec(['nginx', '-s', 'reload'])
        if code != 0:
            raise NginxReloadError(f'nginx reload failed: {output}')

    def answers(self, url: str) -> str | None:
        """What nginx itself answers on url, asked from inside its container"""
        try:
            code, output = self._exec(['curl', '-skf', '-m', '2', url])
        except Exception:
            logger.debug('Could not ask nginx for %s', url, exc_info=True)
            return None
        return output.strip() if code == 0 else None


def apply_config(
    nginx: NginxContainer,
    path: Path,
    text: str | None,
    applied: Callable[[], bool],
    drop_unserved: bool = True,
) -> bool:
    """Write or remove a file and reload, rolling back unless `applied` confirms nginx runs it"""
    previous = _read(path)
    if text is None and not nginx.is_running():
        _write(path, None)
        return True
    if previous == text and nginx.is_running() and applied():
        return True
    try:
        if not nginx.is_running():
            _write(path, text)
        if not nginx.ensure_running():
            raise NginxReloadError('nginx did not start')
        _write(path, text)
        nginx.reload()
        if not wait_for(applied, APPLY_TIMEOUT_SECONDS):
            raise NginxReloadError(f'nginx did not apply {path}')
    except Exception:
        logger.exception('Rolling back %s', path)
        # a file nginx never ran must not stay on disk: at its next start it could stop nginx
        _write(path, None if previous == text and drop_unserved else previous)
        return False
    logger.info('%s %s', 'Removed' if text is None else 'Applied', path)
    return True


class ChainProxyManager:
    """Owns conf.d/chains/<chain>.conf; a change counts only once nginx serves it"""

    def __init__(
        self,
        chain_name: str,
        dutils: DockerUtils | None = None,
        chains_path: Path | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self.chain_name = chain_name
        self.filepath = (chains_path or NGINX_CHAINS_PATH) / f'{chain_name}.conf'
        self.lock_path = lock_path or NGINX_LOCK_PATH
        self.nginx = NginxContainer(dutils=dutils)

    def current(self) -> str | None:
        return _read(self.filepath)

    def serves(self, text: str) -> bool:
        """nginx answers the probe of exactly this file, not an older one or skaled"""
        probe = chain_probe(text)
        return probe is not None and self.nginx.answers(probe[0]) == probe[1]

    def is_synced(self, expected: str | None) -> bool:
        if self.current() != expected:
            return False
        return self._applied(expected)()

    def sync(self, expected: str | None) -> bool:
        """Write the chain file (remove it for None) and reload nginx, serialised across chains"""
        if not self.filepath.parent.is_dir():
            # node-cli has not created the layout, so there is nothing to remove or to serve
            return expected is None
        return locked(
            self.lock_path,
            lambda: apply_config(self.nginx, self.filepath, expected, self._applied(expected)),
        )

    def start_nginx(self) -> bool:
        """Start a stopped nginx, which a chain waiting to move behind it needs first"""
        return locked(self.lock_path, self.nginx.ensure_running)

    def _applied(self, expected: str | None) -> Callable[[], bool]:
        if expected is not None:
            return lambda: self.serves(expected)
        probe = chain_probe(self.current())
        if probe is not None:
            url = probe[0]
        else:
            config = ConfigFileManager(self.chain_name).skaled_config
            if config is None:
                return lambda: not self.nginx.is_running()
            url = get_local_chain_http_endpoint_from_config(config) + PROBE_PATH
        return lambda: (
            not self.nginx.is_running()
            or (
                self.nginx.is_ready()
                and not (self.nginx.answers(url) or '').startswith(f'{self.chain_name} ')
            )
        )

    def remove(self) -> bool:
        return self.sync(None)


def base_fingerprint(text: str) -> str | None:
    first_line = text.split('\n', 1)[0]
    return first_line.removeprefix(BASE_HEADER) if first_line.startswith(BASE_HEADER) else None


def reload_node_proxy(dutils: DockerUtils | None = None) -> bool:
    """Re-render base.conf as node-cli does and reload; False when nginx did not take it"""
    if not NGINX_BASE_CONFIG_FILEPATH.parent.is_dir():
        logger.warning('nginx layout is missing, node-cli reloads nginx itself')
        return True
    ssl_on, skale_node = is_ssl_on(), not is_fair()
    text = render_base_config(ssl_on, skale_node)
    answer = f'base {base_fingerprint(text)}'
    nginx = NginxContainer(dutils=dutils)
    return locked(
        NGINX_LOCK_PATH,
        lambda: apply_config(
            nginx,
            NGINX_BASE_CONFIG_FILEPATH,
            text,
            applied=lambda: nginx.answers(BASE_PROBE_URL) == answer,
            drop_unserved=False,
        ),
    )
