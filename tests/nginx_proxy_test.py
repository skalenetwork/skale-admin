import socket
import time
from pathlib import Path
from unittest import mock

import docker
import pytest
from filelock import FileLock

from core.config.endpoint import get_internal_chain_ports, get_local_chain_http_endpoint_from_config
from core.firewall import IpRange
from core.nginx import (
    ChainProxyConfig,
    ChainProxyManager,
    NginxContainer,
    build_chain_proxy_config,
    chain_ident,
    get_nginx_params,
    ips_to_cidrs,
    is_rpc_proxy_enabled,
    is_rpc_proxy_mode_changed,
    ranges_to_cidrs,
    reload_node_proxy,
    target_rpc_proxy_mode,
)
from core.nginx import params as nginx_params
from core.nginx.config import render_base_config
from core.nginx.manager import NginxReloadError, base_fingerprint, base_probe_urls, chain_probe
from tools.constants import CONFIG_FOLDER

TEMPLATE = Path(CONFIG_FOLDER) / 'chain.conf.j2'
PORTS = {'http': 10003, 'ws': 10002, 'https': 10008, 'wss': 10007}
LIMITS = {
    'per_client_rps': 1000,
    'burst': 200,
    'per_client_sustained_rps': 600,
    'sustained_burst': 24000,
    'global_rps': 5000,
    'global_burst': 2000,
    'conn_per_client': 64,
    'ws_handshake_burst': 50,
    'ws_conn_per_client': 32,
    'ws_conn_total': 20000,
    'max_batch': 128,
    'heavy_rps': 100,
    'ban_short_s': 10,
    'ban_long_s': 30,
}


def make_config(**kwargs) -> ChainProxyConfig:
    data = {
        'chain_name': 'elated-tan-skat',
        'ports': PORTS,
        'peers': ['1.1.1.1/32'],
        'exempt_ips': [],
        'ssl': False,
        'njs': False,
        'limits': LIMITS,
    }
    data.update(kwargs)
    return ChainProxyConfig(**data)


def chain_answers(text: str) -> dict[str, str]:
    probe = chain_probe(text)
    return dict([probe]) if probe else {}


def base_answers(text: str) -> dict[str, str]:
    return {url: f'base {base_fingerprint(text)}' for url in base_probe_urls(False, True)}


class FakeNginx:
    """Answers for the file it loaded at its last accepted reload or start, like nginx"""

    def __init__(self, filepath: Path, answers_for=chain_answers) -> None:
        self.filepath = filepath
        self.answers_for = answers_for
        self.running = True
        self.can_start = True
        self.config_ok = True
        # a listener port held elsewhere: `nginx -s reload` exits 0, nginx keeps its old config
        self.port_busy = False
        self.loaded: str | None = None
        self.reloads = 0

    def _load(self) -> None:
        self.loaded = self.filepath.read_text() if self.filepath.exists() else None

    def is_running(self) -> bool:
        return self.running

    def ensure_running(self) -> bool:
        if not self.running and self.can_start:
            self.running = True
            self._load()
        return self.running

    def reload(self) -> None:
        self.reloads += 1
        if not self.config_ok:
            raise NginxReloadError('nginx config test failed')
        if not self.port_busy:
            self._load()

    def answers(self, url: str) -> str | None:
        if not self.running or self.loaded is None:
            return None
        return self.answers_for(self.loaded).get(url)


@pytest.fixture
def proxy_manager(tmp_path):
    chains_path = tmp_path / 'chains'
    chains_path.mkdir()
    manager = ChainProxyManager(
        'elated-tan-skat',
        dutils=mock.Mock(),
        chains_path=chains_path,
        lock_path=tmp_path / '.chains.lock',
    )
    manager.nginx = FakeNginx(manager.filepath)
    with (
        mock.patch('core.nginx.manager.APPLY_TIMEOUT_SECONDS', 0.2),
        mock.patch('core.nginx.manager.POLL_INTERVAL_SECONDS', 0.05),
    ):
        yield manager


@pytest.fixture
def nginx_layout(tmp_path):
    chains_path = tmp_path / 'chains'
    chains_path.mkdir()
    with mock.patch('core.nginx.params.NGINX_CHAINS_PATH', chains_path):
        yield chains_path


def test_internal_ports_and_local_endpoint(schain_config):
    assert get_internal_chain_ports(PORTS) == {
        'http': 10035,
        'ws': 10034,
        'https': 10040,
        'wss': 10039,
    }
    assert get_local_chain_http_endpoint_from_config(schain_config) == 'http://127.0.0.1:10003'
    assert (
        get_local_chain_http_endpoint_from_config(schain_config, rpc_proxy_mode=True)
        == 'http://127.0.0.1:10035'
    )


def test_chain_ident():
    assert chain_ident('elated-tan-skat') == 'elated_tan_skat'
    assert chain_ident('fair-testnet2') == 'fair_testnet2'


def test_ranges_to_cidrs():
    ranges = [IpRange('10.0.0.0', '10.0.0.3'), IpRange('10.0.1.1', '10.0.1.2')]
    assert ranges_to_cidrs(ranges) == ['10.0.0.0/30', '10.0.1.1/32', '10.0.1.2/32']


def test_template_data():
    data = make_config(
        peers=['2.2.2.2/32', '1.1.1.1/32', '2.2.2.2/32', '10.0.0.0/30'],
        exempt_ips=['10.0.0.1', '3.3.3.3', '3.3.3.3'],
    ).template_data()
    assert data['id'] == 'elated_tan_skat'
    assert (data['http_port'], data['ws_port']) == (10003, 10002)
    assert (data['http_internal'], data['ws_internal']) == (10035, 10034)
    assert data['peers'] == ['1.1.1.1/32', '2.2.2.2/32', '10.0.0.0/30']
    # an exempt address inside a peer network stays a peer
    assert data['exempt_ips'] == ['127.0.0.1', '3.3.3.3']
    assert data['client_rpm'] == 60000
    assert data['global_rpm'] == 300000


def test_render():
    text = make_config(exempt_ips=['3.3.3.3']).render(TEMPLATE)
    assert 'server 127.0.0.1:10035;' in text
    assert 'server 127.0.0.1:10034;' in text
    assert 'listen 10003;' in text
    assert 'listen 10002;' in text
    assert '1.1.1.1/32 peer;' in text
    assert '3.3.3.3/32 exempt;' in text
    assert '127.0.0.1/32 exempt;' in text
    assert 'ssl' not in text
    assert 'js_content' not in text
    assert 'proxy_pass http://elated_tan_skat_http;' in text
    assert 'if ($rpc_class_elated_tan_skat = peer) {' in text
    assert 'location @rpc_peer {' in text

    text = make_config(ssl=True, njs=True).render(TEMPLATE)
    # peers never reach njs, whose subrequest buffer is far below a snapshot chunk
    assert 'location @rpc_peer {' in text
    assert 'listen 10008 ssl;' in text
    assert 'listen 10007 ssl;' in text
    assert 'js_content rpc.handle;' in text
    assert 'proxy_pass http://elated_tan_skat_http/;' in text
    assert 'set $rpc_client_rpm  60000;' in text


def test_build_chain_proxy_config(tmp_path):
    node_info = {
        'httpRpcPort': 10003,
        'wsRpcPort': 10002,
        'httpsRpcPort': 10008,
        'wssRpcPort': 10007,
    }
    params = {'njs': True, 'exempt_hosts': ['a.example'], 'limits': LIMITS}
    with (
        mock.patch('core.nginx.config.get_nginx_params', return_value=params),
        mock.patch('core.nginx.config.resolve_exempt_hosts', return_value=['3.3.3.3']) as resolve,
        mock.patch('core.nginx.config.SSL_CERT_PATH', tmp_path / 'ssl_cert'),
    ):
        config = build_chain_proxy_config(
            'elated-tan-skat', {'skaleConfig': {'nodeInfo': node_info}}, ips_to_cidrs(['1.1.1.1'])
        )
    assert config == make_config(exempt_ips=['3.3.3.3'], njs=True)
    resolve.assert_called_once_with(['a.example'])


def test_get_nginx_params():
    params = get_nginx_params()
    assert params['rpc_proxy'] is False
    assert params['limits']['max_batch'] == 128


def test_is_rpc_proxy_enabled(nginx_layout):
    params = {'rpc_proxy': False, 'limits': LIMITS}
    with (
        mock.patch('core.nginx.params.get_nginx_params', return_value=params),
        mock.patch('core.nginx.params.NodeOptions') as node_options,
    ):
        node_options.return_value.rpc_proxy = None
        assert not is_rpc_proxy_enabled()
        params['rpc_proxy'] = True
        assert is_rpc_proxy_enabled()
        # the per-node override wins in both directions
        node_options.return_value.rpc_proxy = False
        assert not is_rpc_proxy_enabled()
        params['rpc_proxy'] = False
        node_options.return_value.rpc_proxy = True
        assert is_rpc_proxy_enabled()


def test_is_rpc_proxy_enabled_needs_layout_and_params(tmp_path, nginx_layout):
    with mock.patch('core.nginx.params.NodeOptions') as node_options:
        node_options.return_value.rpc_proxy = True
        with mock.patch('core.nginx.params.get_nginx_params', return_value={}):
            assert not is_rpc_proxy_enabled()
        with (
            mock.patch('core.nginx.params.get_nginx_params', return_value={'limits': LIMITS}),
            mock.patch('core.nginx.params.NGINX_CHAINS_PATH', tmp_path / 'missing'),
        ):
            assert not is_rpc_proxy_enabled()


@pytest.mark.parametrize(
    'current, enabled, nginx_running, target',
    [
        # moving behind nginx needs nginx to take over the public ports
        (False, True, True, True),
        (False, True, False, False),
        (False, False, True, False),
        # behind nginx, only the flag moves skaled back, an nginx restart does not
        (True, True, False, True),
        (True, True, True, True),
        (True, False, True, False),
        (True, False, False, False),
    ],
)
def test_target_rpc_proxy_mode(current, enabled, nginx_running, target):
    with (
        mock.patch('core.nginx.mode.is_rpc_proxy_enabled', return_value=enabled),
        mock.patch('core.nginx.mode.NginxContainer.is_running', return_value=nginx_running),
    ):
        assert target_rpc_proxy_mode(current, dutils=mock.Mock()) is target
        record = mock.Mock(rpc_proxy_mode=current)
        assert is_rpc_proxy_mode_changed(record, dutils=mock.Mock()) is (current != target)


def test_resolve_exempt_hosts():
    nginx_params._resolved_hosts.clear()
    addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.2.3.4', 0))] * 2
    with mock.patch('core.nginx.params.socket.getaddrinfo', return_value=addrinfo) as resolve:
        assert nginx_params.resolve_exempt_hosts(['a.example']) == ['1.2.3.4']
        assert nginx_params.resolve_exempt_hosts(['a.example']) == ['1.2.3.4']
        assert resolve.call_count == 1
    later = time.monotonic() + 2 * nginx_params.EXEMPT_HOSTS_TTL_SECONDS
    with (
        mock.patch('core.nginx.params.socket.getaddrinfo', side_effect=socket.gaierror),
        mock.patch('core.nginx.params.time.monotonic', return_value=later),
    ):
        # the last answer is kept while DNS fails, an unknown host is skipped
        assert nginx_params.resolve_exempt_hosts(['a.example', 'b.example']) == ['1.2.3.4']
    nginx_params._resolved_hosts.clear()


def test_sync_writes_and_reloads(proxy_manager):
    nginx = proxy_manager.nginx
    text = make_config().render(TEMPLATE)
    assert proxy_manager.is_synced(None)
    assert proxy_manager.remove()
    assert nginx.reloads == 0
    assert proxy_manager.sync(text)
    assert proxy_manager.current() == text
    assert proxy_manager.is_synced(text)
    assert nginx.reloads == 1
    assert proxy_manager.sync(text)
    assert nginx.reloads == 1
    assert proxy_manager.remove()
    assert proxy_manager.current() is None
    assert nginx.loaded is None
    assert nginx.reloads == 2


def test_rendered_file_names_its_probe():
    text = make_config().render(TEMPLATE)
    url, answer = chain_probe(text)
    assert url == 'http://127.0.0.1:10003/.skale-proxy'
    assert f"return 200 '{answer}';" in text
    # any change to the file changes what nginx has to answer
    other = make_config(peers=['2.2.2.2/32']).render(TEMPLATE)
    assert chain_probe(other)[1] != answer


def test_sync_rolls_back_when_config_test_fails(proxy_manager):
    text = make_config().render(TEMPLATE)
    assert proxy_manager.sync(text)
    proxy_manager.nginx.config_ok = False
    assert not proxy_manager.sync(make_config(peers=['2.2.2.2/32']).render(TEMPLATE))
    assert proxy_manager.current() == text
    # removal is rolled back too, so the next attempt reloads again
    assert not proxy_manager.remove()
    assert proxy_manager.current() == text


def test_sync_detects_reload_nginx_rejected(proxy_manager):
    nginx = proxy_manager.nginx
    text = make_config().render(TEMPLATE)
    nginx.port_busy = True
    # the reload signal succeeds, but nginx never serves the file
    assert not proxy_manager.sync(text)
    assert proxy_manager.current() is None
    assert not proxy_manager.is_synced(text)
    nginx.port_busy = False
    assert proxy_manager.sync(text)
    assert proxy_manager.is_synced(text)

    # nginx keeps serving a removed file while the port stays with it
    nginx.port_busy = True
    assert not proxy_manager.remove()
    assert proxy_manager.current() == text


def test_sync_reapplies_file_nginx_does_not_serve(proxy_manager):
    nginx = proxy_manager.nginx
    text = make_config().render(TEMPLATE)
    # on disk but never loaded, as left by a reload that nginx rejected
    proxy_manager.filepath.write_text(text)
    assert not proxy_manager.is_synced(text)
    assert proxy_manager.sync(text)
    assert proxy_manager.is_synced(text)

    nginx.loaded = None
    nginx.port_busy = True
    assert not proxy_manager.sync(text)
    # never served, so it must not wait on disk for the next nginx start
    assert proxy_manager.current() is None


def test_sync_starts_stopped_nginx(proxy_manager):
    nginx = proxy_manager.nginx
    text = make_config().render(TEMPLATE)
    assert proxy_manager.sync(text)
    nginx.running = False
    assert not proxy_manager.is_synced(text)
    # unchanged file: starting nginx is all it takes
    assert proxy_manager.sync(text)
    assert nginx.running
    assert proxy_manager.is_synced(text)

    nginx.running = False
    other = make_config(peers=['2.2.2.2/32']).render(TEMPLATE)
    assert proxy_manager.sync(other)
    assert proxy_manager.is_synced(other)


def test_start_nginx(proxy_manager):
    nginx = proxy_manager.nginx
    nginx.running = False
    assert proxy_manager.start_nginx()
    assert nginx.running
    nginx.running = False
    nginx.can_start = False
    assert not proxy_manager.start_nginx()


def test_sync_with_nginx_that_cannot_start(proxy_manager):
    nginx = proxy_manager.nginx
    nginx.running = False
    nginx.can_start = False
    text = make_config().render(TEMPLATE)
    assert not proxy_manager.sync(text)
    assert proxy_manager.current() is None
    proxy_manager.filepath.write_text(text)
    assert not proxy_manager.is_synced(text)
    # nothing holds the ports, removal is safe without nginx
    assert proxy_manager.remove()
    assert proxy_manager.current() is None
    assert nginx.reloads == 0


def test_sync_without_layout(tmp_path):
    manager = ChainProxyManager(
        'elated-tan-skat',
        dutils=mock.Mock(),
        chains_path=tmp_path / 'missing',
        lock_path=tmp_path / 'missing' / '.chains.lock',
    )
    assert manager.remove()
    assert not manager.sync('a')


def test_sync_gives_up_on_held_lock(proxy_manager):
    with (
        FileLock(proxy_manager.lock_path),
        mock.patch('core.nginx.manager.LOCK_TIMEOUT_SECONDS', 0.1),
    ):
        assert not proxy_manager.sync(make_config().render(TEMPLATE))
    assert proxy_manager.current() is None


def exec_result(exit_code: int, output: bytes = b'') -> mock.Mock:
    return mock.Mock(exit_code=exit_code, output=output)


def test_nginx_container_reload_and_answers():
    dutils = mock.Mock()
    exec_run = dutils.client.containers.get.return_value.exec_run
    nginx = NginxContainer(dutils=dutils)

    exec_run.side_effect = [exec_result(0), exec_result(0)]
    nginx.reload()
    assert exec_run.call_args_list == [
        mock.call(['nginx', '-t']),
        mock.call(['nginx', '-s', 'reload']),
    ]
    exec_run.side_effect = [exec_result(1, b'unknown directive')]
    with pytest.raises(NginxReloadError, match='config test failed: unknown directive'):
        nginx.reload()
    exec_run.side_effect = [exec_result(0), exec_result(1, b'no master process')]
    with pytest.raises(NginxReloadError, match='reload failed: no master process'):
        nginx.reload()

    url = 'http://127.0.0.1:3009/.skale-proxy'
    exec_run.side_effect = [
        exec_result(0, b'base 0123\n'),
        exec_result(7),
        docker.errors.APIError(''),
    ]
    assert nginx.answers(url) == 'base 0123'
    assert nginx.answers(url) is None
    assert nginx.answers(url) is None
    assert exec_run.call_args == mock.call(['curl', '-skf', '-m', '2', url])


def test_nginx_container_ensure_running():
    dutils = mock.Mock()
    restart = dutils.client.containers.get.return_value.restart
    nginx = NginxContainer(dutils=dutils)
    dutils.is_container_running.side_effect = [True]
    assert nginx.ensure_running()
    restart.assert_not_called()

    # a failing status check counts as not running yet
    dutils.is_container_running.side_effect = [False, docker.errors.APIError(''), True]
    with mock.patch('core.nginx.manager.POLL_INTERVAL_SECONDS', 0.01):
        assert nginx.ensure_running()
    restart.assert_called_once()

    dutils.is_container_running.side_effect = [False]
    restart.side_effect = docker.errors.APIError('')
    assert not nginx.ensure_running()


def test_base_probe_urls():
    assert base_probe_urls(False, False) == ['http://127.0.0.1:3009/.skale-proxy']
    assert base_probe_urls(True, True) == [
        'http://127.0.0.1:3009/.skale-proxy',
        'https://127.0.0.1:311/.skale-proxy',
        'http://127.0.0.1:80/.skale-proxy',
        'https://127.0.0.1:443/.skale-proxy',
    ]


def test_render_base_config(tmp_path):
    cert = tmp_path / 'ssl_cert'
    with mock.patch('core.nginx.config.SSL_CERT_PATH', cert):
        fair = render_base_config(ssl_on=False, skale_node=False)
        cert.write_text('first')
        first = render_base_config(ssl_on=True, skale_node=True)
        cert.write_text('second')
        second = render_base_config(ssl_on=True, skale_node=True)
    assert 'listen 80;' not in fair
    assert 'listen 443 ssl;' in first
    fingerprint = base_fingerprint(first)
    assert first.count(f"return 200 'base {fingerprint}';") == 2
    # a new certificate is a new file for nginx to answer for
    assert base_fingerprint(second) != fingerprint
    assert base_fingerprint('server {}') is None


@pytest.fixture
def base_nginx(tmp_path):
    filepath = tmp_path / 'conf.d' / 'base.conf'
    filepath.parent.mkdir()
    nginx = FakeNginx(filepath, answers_for=base_answers)
    with (
        mock.patch('core.nginx.manager.NGINX_BASE_CONFIG_FILEPATH', filepath),
        mock.patch('core.nginx.manager.NGINX_LOCK_PATH', tmp_path / '.chains.lock'),
        mock.patch('core.nginx.manager.NginxContainer', return_value=nginx),
        mock.patch('core.nginx.manager.is_ssl_on', return_value=False),
        mock.patch('core.nginx.manager.is_fair', return_value=False),
        mock.patch('core.nginx.manager.APPLY_TIMEOUT_SECONDS', 0.2),
        mock.patch('core.nginx.manager.POLL_INTERVAL_SECONDS', 0.05),
    ):
        yield nginx


def test_reload_node_proxy(base_nginx):
    stale = render_base_config(ssl_on=False, skale_node=False)
    base_nginx.filepath.write_text(stale)
    base_nginx.loaded = stale
    base_nginx.port_busy = True
    # nginx keeps the file it runs, and so does the disk
    assert not reload_node_proxy()
    assert base_nginx.filepath.read_text() == stale

    base_nginx.port_busy = False
    assert reload_node_proxy()
    assert base_nginx.loaded == base_nginx.filepath.read_text() != stale
    assert reload_node_proxy()
    assert base_nginx.reloads == 2

    with (
        FileLock(base_nginx.filepath.parent.parent / '.chains.lock'),
        mock.patch('core.nginx.manager.LOCK_TIMEOUT_SECONDS', 0.1),
    ):
        assert not reload_node_proxy()


def test_reload_node_proxy_without_layout(tmp_path):
    missing = tmp_path / 'missing' / 'base.conf'
    with mock.patch('core.nginx.manager.NGINX_BASE_CONFIG_FILEPATH', missing):
        assert reload_node_proxy()
    assert not missing.exists()
