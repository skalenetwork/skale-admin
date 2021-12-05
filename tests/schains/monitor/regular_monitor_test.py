import logging
import platform

import mock

from skale.schain_config.generator import get_nodes_for_schain
from skale.wallets import SgxWallet
from skale.utils.helper import ip_from_bytes

from core.schains.checks import SChainChecks
from core.schains.monitor import RegularMonitor
from core.schains.ima import ImaData
from core.schains.runner import get_container_name


from tools.configs import (
    SGX_CERTIFICATES_FOLDER,
    SGX_SERVER_URL
)

from web.models.schain import SChainRecord

from tests.dkg_utils import safe_run_dkg_mock
from tests.utils import alter_schain_config


logger = logging.getLogger(__name__)


def test_regular_monitor(schain_db, skale, node_config, skale_ima, dutils, ssl_folder,
                         rule_controller,
                         schain_on_contracts):
    schain_name = schain_on_contracts
    schain = skale.schains.get_by_name(schain_name)
    nodes = get_nodes_for_schain(skale, schain_name)

    sgx_wallet = SgxWallet(
        web3=skale.web3,
        sgx_endpoint=SGX_SERVER_URL,
        path_to_cert=SGX_CERTIFICATES_FOLDER
    )

    node_config.id = nodes[0]['id']
    node_config.ip = ip_from_bytes(nodes[0]['ip'])
    node_config.sgx_key_name = sgx_wallet.key_name

    schain_record = SChainRecord.get_by_name(schain_name)
    schain_checks = SChainChecks(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )
    ima_data = ImaData(False, '0x1')
    test_monitor = RegularMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks,
        rule_controller=rule_controller,
        dutils=dutils
    )

    with mock.patch('core.schains.monitor.base_monitor.safe_run_dkg', safe_run_dkg_mock):
        test_monitor.run()

    container = dutils.safe_get_container(
        get_container_name('schain', schain_name)
    )
    # separator = b'=' * 80 + b'\n'
    tail_lines = container.logs(tail=300)
    # lines_number = len(io.BytesIO(tail_lines).readlines())
    # head = min(lines_number, head)
    # log_stream = container.logs(stream=True, follow=True)
    # head_lines = b''.join(itertools.islice(log_stream, head))
    print(tail_lines)
    assert schain_checks.config_dir.status
    assert schain_checks.dkg.status
    assert schain_checks.config.status
    assert schain_checks.volume.status
    assert schain_checks.skaled_container.status
    assert not schain_checks.ima_container.status

    test_monitor.cleanup_schain_docker_entity()
    alter_schain_config(schain_name, sgx_wallet.public_key)

    test_monitor.run()

    assert schain_checks.volume.status
    assert schain_checks.skaled_container.status

    if platform.system() != 'Darwin':  # not working due to the macOS networking in Docker
        assert schain_checks.rpc.status
        assert schain_checks.blocks.status

    test_monitor.cleanup_schain_docker_entity()
