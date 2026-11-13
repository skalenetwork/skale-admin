from core.chain.cmd import get_skaled_container_cmd, get_snapshot_opts
from core.chain.ssl import get_ssl_filepath
from core.config.schain.main import get_skaled_container_config_path
from tools.constants.containers import SHARED_SPACE_CONTAINER_PATH


def test_get_skaled_container_cmd(schain_config, cert_key_pair, st):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_skaled_container_cmd(schain_name)
    config_filepath = get_skaled_container_config_path(schain_name)
    ssl_key_path, ssl_cert_path = get_ssl_filepath()
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {st.endpoint} '
        f'--sgx-url {st.sgx_url} --shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data '
        '-v 3 --web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path}'
    )
    assert container_opts == expected_opts

    container_opts = get_skaled_container_cmd(schain_name, enable_ssl=False)
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {st.endpoint} '
        f'--sgx-url {st.sgx_url} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data -v 3 --web3-trace '
        f'--enable-debug-behavior-apis --aa no'
    )
    assert container_opts == expected_opts

    container_opts = get_skaled_container_cmd(schain_name, snapshot_from='1.1.1.1')
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {st.endpoint} '
        f'--sgx-url {st.sgx_url} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data -v 3 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path} '
        '--no-snapshot-majority 1.1.1.1'
    )
    assert container_opts == expected_opts

    container_opts = get_skaled_container_cmd(schain_name, snapshot_from='')
    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {st.endpoint} '
        f'--sgx-url {st.sgx_url} '
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data -v 3 '
        f'--web3-trace --enable-debug-behavior-apis '
        f'--aa no --ssl-key {ssl_key_path} --ssl-cert {ssl_cert_path}'
    )
    assert container_opts == expected_opts


def test_get_skaled_container_cmd_without_certificates(schain_config, ssl_folder, st):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    # skaled drops options with a NULL value, and then listens on no TLS port
    assert get_skaled_container_cmd(schain_name).endswith('--ssl-key NULL --ssl-cert NULL')


def test_get_snapshot_opts():
    sync_opts = get_snapshot_opts(start_ts=123)
    assert sync_opts == ['--download-snapshot readfromconfig', '--start-timestamp 123']
    sync_opts = get_snapshot_opts()
    assert sync_opts == ['--download-snapshot readfromconfig']


def test_get_skaled_container_cmd_passive_node(schain_config, cert_key_pair, st):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_skaled_container_cmd(schain_name, enable_ssl=False, passive_node=True)
    config_filepath = get_skaled_container_config_path(schain_name)

    expected_opts = (
        f'--config {config_filepath} -d /data_dir --ipcpath /data_dir --http-port 10003 '
        f'--https-port 10008 --ws-port 10002 --wss-port 10007 --main-net-url {st.endpoint} '
        f'-v 3 --web3-trace --enable-debug-behavior-apis --aa no'
    )
    assert container_opts == expected_opts


def test_get_skaled_container_cmd_rpc_proxy(schain_config, cert_key_pair, st):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    container_opts = get_skaled_container_cmd(schain_name, rpc_proxy=True)
    proxied = '--http-port 10035 --https-port 10040 --ws-port 10034 --wss-port 10039 --rpc-loopback'
    assert proxied in container_opts
    # nginx terminates TLS
    assert '--ssl-' not in container_opts
    public_opts = get_skaled_container_cmd(schain_name)
    assert '--http-port 10003 --https-port 10008 --ws-port 10002 --wss-port 10007' in public_opts
    assert '--rpc-loopback' not in public_opts
    assert '--ssl-key' in public_opts
