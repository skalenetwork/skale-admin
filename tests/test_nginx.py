import contextlib
import shutil
import time
from pathlib import Path
from unittest import mock

import docker
import pytest
from jinja2 import Environment

from core.nginx import ChainProxyConfig, ChainProxyManager, reload_node_proxy
from core.nginx.manager import base_fingerprint
from tools.constants import CONFIG_FOLDER, NGINX_CONTAINER_NAME

NGINX_IMAGE = 'nginx:1.29.5'
CHAIN = 'test-chain'
PORTS = {'http': 10003, 'ws': 10002, 'https': 10008, 'wss': 10007}
# one request per second without burst, so the second quick request is rejected
LIMITS = {
    'per_client_rps': 1,
    'burst': 0,
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
# stands in for skaled on the internal http port
FAKE_SKALED = """
js_import fake_skaled from /etc/nginx/conf.d/fake_skaled.js;
server {
    listen 127.0.0.1:10035;
    location / {
        js_content fake_skaled.handle;
    }
}
"""
# snapshot fragments are as large as the request asks, like skaled's 100 MiB chunks
FAKE_SKALED_JS = """
function handle(r) {
    const body = JSON.parse(r.requestText || '{}');
    if (body.method === 'skale_downloadSnapshotFragment') {
        r.return(200, 'x'.repeat(body.params.size));
        return;
    }
    r.headersOut['Content-Type'] = 'application/json';
    r.return(200, '{"jsonrpc":"2.0","id":1,"result":"0x1"}');
}
export default { handle: handle };
"""


@pytest.fixture
def nginx_dir():
    config_folder = Path(CONFIG_FOLDER)
    path = config_folder / 'test-nginx'
    (path / 'conf.d' / 'chains').mkdir(parents=True)
    (path / 'njs').mkdir()
    env = Environment()
    for template, dest, data in (
        ('nginx.conf.j2', path / 'nginx.conf', {}),
        ('base.conf.j2', path / 'conf.d' / 'base.conf', {'ssl': False, 'skale_node': True}),
    ):
        dest.write_text(env.from_string((config_folder / template).read_text()).render(data))
    shutil.copy(config_folder / 'njs' / 'rpc.js', path / 'njs' / 'rpc.js')
    (path / 'conf.d' / 'fake_skaled.conf').write_text(FAKE_SKALED)
    (path / 'conf.d' / 'fake_skaled.js').write_text(FAKE_SKALED_JS)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def nginx_container(nginx_dir, dutils):
    dutils.safe_rm(NGINX_CONTAINER_NAME)
    container = dutils.run_container(
        NGINX_IMAGE,
        NGINX_CONTAINER_NAME,
        volumes={
            str(nginx_dir / 'nginx.conf'): {'bind': '/etc/nginx/nginx.conf', 'mode': 'ro'},
            str(nginx_dir / 'conf.d'): {'bind': '/etc/nginx/conf.d', 'mode': 'ro'},
            str(nginx_dir / 'njs'): {'bind': '/etc/nginx/njs', 'mode': 'ro'},
        },
    )
    for _ in range(20):
        if dutils.is_container_running(NGINX_CONTAINER_NAME):
            break
        time.sleep(0.5)
    try:
        yield container
    finally:
        dutils.safe_rm(NGINX_CONTAINER_NAME)


@pytest.fixture
def manager(nginx_dir, dutils):
    return ChainProxyManager(
        CHAIN,
        dutils=dutils,
        chains_path=nginx_dir / 'conf.d' / 'chains',
        lock_path=nginx_dir / '.chains.lock',
    )


def render(njs: bool = False, peers: tuple[str, ...] = ('10.1.1.1/32',)) -> str:
    return ChainProxyConfig(
        chain_name=CHAIN,
        ports=PORTS,
        peers=list(peers),
        exempt_ips=[],
        ssl=False,
        njs=njs,
        limits=LIMITS,
    ).render()


def post(container, host: str, body: str = '{"method":"eth_chainId"}', times: int = 1) -> list:
    """HTTP codes of quick requests to the chain's public http port, made inside the container"""
    curl = (
        f"curl -s -o /dev/null -w '%{{http_code}} ' -H 'Content-Type: application/json' "
        f"-d '{body}' http://{host}:10003/"
    )
    result = container.exec_run(['sh', '-c', f'for i in $(seq {times}); do {curl}; done'])
    return result.output.decode().split()


def container_ip(container) -> str:
    # requests to this address come from it too, so nginx sees a public client
    return container.exec_run(['hostname', '-i']).output.decode().split()[0]


def test_chain_proxy_serves_and_limits(nginx_container, manager):
    text = render()
    assert manager.sync(text)
    assert manager.is_synced(text)

    assert post(nginx_container, container_ip(nginx_container), times=3) == ['200', '429', '429']
    # loopback is exempt from every zone
    assert post(nginx_container, '127.0.0.1', times=3) == ['200', '200', '200']


def test_chain_proxy_keeps_last_good_config(nginx_container, manager):
    text = render()
    assert manager.sync(text)
    assert not manager.sync('server { listen 10003; not_a_directive; }')
    assert manager.current() == text
    assert post(nginx_container, '127.0.0.1') == ['200']


def test_chain_proxy_remove_frees_ports(nginx_container, manager):
    assert manager.sync(render())
    assert manager.remove()
    assert manager.current() is None
    codes = []
    for _ in range(10):
        codes = post(nginx_container, '127.0.0.1')
        if codes == ['000']:
            break
        time.sleep(0.2)
    assert codes == ['000']


def test_chain_proxy_njs_gates_methods(nginx_container, manager):
    assert manager.sync(render(njs=True))
    ip = container_ip(nginx_container)
    assert post(nginx_container, ip, body='{"method":"skale_getSnapshot"}') == ['403']
    assert post(nginx_container, '127.0.0.1', body='{"method":"eth_chainId"}') == ['200']


@pytest.mark.parametrize('njs', [False, True])
def test_chain_proxy_peer_gets_large_snapshot_chunk(nginx_container, manager, njs):
    ip = container_ip(nginx_container)
    # the container reaches itself from its own address, which is now a peer
    assert manager.sync(render(njs=njs, peers=(f'{ip}/32',)))
    size = 12 * 1024 * 1024  # above the 8m njs subrequest buffer
    body = f'{{"method":"skale_downloadSnapshotFragment","params":{{"size":{size}}}}}'
    curl = (
        "curl -s -o /dev/null -w '%{http_code} %{size_download}' "
        f"-H 'Content-Type: application/json' -d '{body}' http://{ip}:10003/"
    )
    result = nginx_container.exec_run(['sh', '-c', curl])
    assert result.output.decode().split() == ['200', str(size)]


@pytest.fixture
def port_holder(nginx_container, dutils):
    """Another process in nginx's network namespace that holds the chain's http port"""
    holder = dutils.client.containers.run(
        'alpine:latest',
        name='test-port-holder',
        detach=True,
        network_mode=f'container:{NGINX_CONTAINER_NAME}',
        command=['sh', '-c', 'while true; do nc -l -p 10003 > /dev/null; done'],
    )
    time.sleep(1)
    try:
        yield holder
    finally:
        with contextlib.suppress(docker.errors.NotFound):
            holder.remove(force=True)


def test_chain_proxy_reload_nginx_rejects_is_not_synced(nginx_container, manager, port_holder):
    text = render()
    # nginx -t and nginx -s reload both succeed, nginx keeps its old config
    assert not manager.sync(text)
    assert manager.current() is None
    assert not manager.is_synced(text)
    logs = nginx_container.logs().decode()
    assert 'bind() to 0.0.0.0:10003 failed' in logs

    port_holder.remove(force=True)
    assert manager.sync(text)
    assert manager.is_synced(text)
    assert post(nginx_container, '127.0.0.1') == ['200']


def test_chain_proxy_starts_stopped_nginx(nginx_container, manager, dutils):
    text = render()
    assert manager.sync(text)
    nginx_container.stop(timeout=1)
    assert not manager.is_synced(text)
    assert manager.sync(text)
    assert dutils.is_container_running(NGINX_CONTAINER_NAME)
    assert manager.is_synced(text)
    nginx_container.reload()
    assert post(nginx_container, '127.0.0.1') == ['200']


def test_node_proxy_reload_is_verified(nginx_container, nginx_dir, dutils):
    filepath = nginx_dir / 'conf.d' / 'base.conf'
    with (
        mock.patch('core.nginx.manager.NGINX_BASE_CONFIG_FILEPATH', filepath),
        mock.patch('core.nginx.manager.NGINX_LOCK_PATH', nginx_dir / '.chains.lock'),
        mock.patch('core.nginx.manager.is_ssl_on', return_value=False),
        mock.patch('core.nginx.manager.is_fair', return_value=False),
    ):
        assert reload_node_proxy(dutils)
    answer = f'base {base_fingerprint(filepath.read_text())}'
    for port in (3009, 80):
        probe = nginx_container.exec_run(['curl', '-s', f'http://127.0.0.1:{port}/.skale-proxy'])
        assert probe.output.decode() == answer
