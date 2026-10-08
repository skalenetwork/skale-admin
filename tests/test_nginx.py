import contextlib
import json
import shutil
import time
from pathlib import Path
from unittest import mock

import docker
import pytest
from jinja2 import Environment

from core.nginx import ChainProxyConfig, ChainProxyManager, reload_node_proxy
from core.nginx.manager import base_fingerprint, wait_for
from tools.constants import CONFIG_FOLDER, NGINX_CONTAINER_NAME, NGINX_TEMPLATE_DIR

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
    'ban_s': 10,
}
EXIT_TIME_CALL = '{"method":"setSchainExitTime","params":{"finishTime":1}}'
# stands in for skaled on the internal http and ws ports
FAKE_SKALED = """
js_import fake_skaled from /etc/nginx/conf.d/fake_skaled.js;
server {
    listen 127.0.0.1:10035;
    location / {
        js_content fake_skaled.handle;
    }
}
server {
    listen 127.0.0.1:10034;
    location / {
        return 200 '$http_upgrade $http_connection';
    }
}
"""
# answers are as large as the request asks, like skaled's 100 MiB snapshot chunks
FAKE_SKALED_JS = """
function handle(r) {
    const body = JSON.parse(r.requestText || '{}');
    if (body.params && body.params.size) {
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
        dest.write_text(env.from_string((NGINX_TEMPLATE_DIR / template).read_text()).render(data))
    shutil.copy(NGINX_TEMPLATE_DIR / 'njs' / 'rpc.js', path / 'njs' / 'rpc.js')
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
        ssl=False,
        njs=njs,
        limits=LIMITS,
    ).render()


def post(
    container,
    host: str,
    body: str = '{"method":"eth_chainId"}',
    times: int = 1,
    method: str = 'POST',
) -> list:
    """HTTP codes of quick requests to the chain's public http port, made inside the container"""
    curl = (
        f"curl -s -o /dev/null -w '%{{http_code}} ' -X {method} "
        f"-H 'Content-Type: application/json' -d '{body}' http://{host}:10003/"
    )
    result = container.exec_run(['sh', '-c', f'for i in $(seq {times}); do {curl}; done'])
    return result.output.decode().split()


def curl(container, url: str, *options: str) -> str:
    return container.exec_run(['curl', '-s', *options, url]).output.decode()


def container_ip(container) -> str:
    # requests to this address come from it too, so nginx sees a public client
    return container.exec_run(['hostname', '-i']).output.decode().split()[0]


def test_chain_proxy_serves_and_limits(nginx_container, manager):
    text = render()
    assert manager.sync(text)
    assert manager.is_synced(text)

    ip = container_ip(nginx_container)
    assert post(nginx_container, ip, times=3) == ['200', '429', '429']
    assert json.loads(curl(nginx_container, f'http://{ip}:10003/', '-d', '{}')) == {
        'jsonrpc': '2.0',
        'id': None,
        'error': {'code': -32005, 'message': 'rate limited'},
    }
    # loopback is exempt from every zone
    assert post(nginx_container, '127.0.0.1', times=3) == ['200', '200', '200']
    assert (
        curl(
            nginx_container,
            f'http://{ip}:10003/.skale-proxy',
            '-o',
            '/dev/null',
            '-w',
            '%{http_code}',
        )
        == '403'
    )


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


def test_chain_proxy_removes_listener_after_file_loss(nginx_container, manager):
    assert manager.sync(render())
    manager.filepath.unlink()
    config = {'skaleConfig': {'nodeInfo': {'httpRpcPort': 10003, 'wsRpcPort': 10002}}}
    with mock.patch('core.nginx.manager.ConfigFileManager') as cfm:
        cfm.return_value.skaled_config = config
        assert not manager.is_synced(None)
        assert manager.remove()
        assert manager.is_synced(None)
    assert post(nginx_container, '127.0.0.1') == ['000']


def test_chain_proxy_repairs_config_that_prevents_start(nginx_container, manager):
    assert manager.sync(render())
    nginx_container.stop(timeout=1)
    manager.filepath.write_text(
        'server { listen 10008 ssl; ssl_certificate /missing; ssl_certificate_key /missing; }'
    )
    text = render()
    assert manager.sync(text)
    assert manager.is_synced(text)
    assert post(nginx_container, '127.0.0.1') == ['200']


@pytest.mark.parametrize('peer', [False, True])
def test_chain_proxy_blocks_loopback_trusted_method(nginx_container, manager, peer):
    ip = container_ip(nginx_container)
    assert manager.sync(render(peers=(f'{ip}/32',) if peer else ()))
    # skaled trusts loopback callers, and every proxied call reaches it from loopback
    assert post(nginx_container, ip, body=EXIT_TIME_CALL) == ['403']
    batch = f'[{{"method":"eth_chainId"}},{EXIT_TIME_CALL}]'
    assert post(nginx_container, '127.0.0.1', body=batch) == ['403']
    assert post(nginx_container, '127.0.0.1', body=EXIT_TIME_CALL, method='PUT') == ['403']
    # what njs cannot read is never passed on
    assert post(nginx_container, '127.0.0.1', body='not json') == ['400']
    assert post(nginx_container, '127.0.0.1', method='OPTIONS') == ['200']


def test_chain_proxy_njs_gates_methods(nginx_container, manager):
    assert manager.sync(render(njs=True))
    ip = container_ip(nginx_container)
    assert post(nginx_container, ip, body='{"method":"skale_getSnapshot"}') == ['403']
    gated = '{"method":"skale_getSnapshot"}'
    assert post(nginx_container, '127.0.0.1', body=gated, method='PUT') == ['403']
    assert post(nginx_container, '127.0.0.1', body='{"method":"eth_chainId"}') == ['200']
    calls = ','.join(['{"method":"eth_chainId"}'] * (LIMITS['max_batch'] + 1))
    assert post(nginx_container, '127.0.0.1', body=f'[{calls}]') == ['400']


def test_chain_proxy_njs_bans_over_budget(nginx_container, manager):
    assert manager.sync(render(njs=True))
    ip = container_ip(nginx_container)
    two_calls = '[{"method":"eth_chainId"},{"method":"eth_chainId"}]'
    # one request for limit_req, two calls for the njs budget of one per second
    assert post(nginx_container, ip, body=two_calls) == ['429']
    time.sleep(1.1)
    assert post(nginx_container, ip) == ['429']
    # loopback skips the budgets
    assert post(nginx_container, '127.0.0.1', body=two_calls) == ['200']


@pytest.mark.parametrize('njs', [False, True])
@pytest.mark.parametrize('peer', [False, True])
def test_chain_proxy_streams_large_answers(nginx_container, manager, njs, peer):
    ip = container_ip(nginx_container)
    # the container reaches itself from its own address, a peer when listed
    assert manager.sync(render(njs=njs, peers=(f'{ip}/32',) if peer else ()))
    method = 'skale_downloadSnapshotFragment' if peer else 'eth_getBlockByNumber'
    size = 12 * 1024 * 1024
    body = f'{{"method":"{method}","params":{{"size":{size}}}}}'
    answer = curl(
        nginx_container,
        f'http://{ip}:10003/',
        '-o',
        '/dev/null',
        '-w',
        '%{http_code} %{size_download}',
        '-d',
        body,
    )
    assert answer.split() == ['200', str(size)]


def test_chain_proxy_upgrades_websockets(nginx_container, manager):
    assert manager.sync(render())
    upgrade = ('-H', 'Upgrade: websocket', '-H', 'Connection: Upgrade')
    assert curl(nginx_container, 'http://127.0.0.1:10002/', *upgrade) == 'websocket upgrade'


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
    listening = ['sh', '-c', 'netstat -ltn | grep -q ":10003 "']
    assert wait_for(lambda: holder.exec_run(listening).exit_code == 0, 10)
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
    ip = container_ip(nginx_container)
    for port in (3009, 80):
        assert curl(nginx_container, f'http://127.0.0.1:{port}/.skale-proxy') == answer
        code = curl(
            nginx_container,
            f'http://{ip}:{port}/.skale-proxy',
            '-o',
            '/dev/null',
            '-w',
            '%{http_code}',
        )
        assert code == '403'
