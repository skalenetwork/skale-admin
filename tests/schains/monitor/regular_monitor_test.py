import logging
import platform

from skale.schain_config.generator import get_nodes_for_schain
from skale.wallets import SgxWallet
from skale.utils.helper import ip_from_bytes

from core.schains.checks import SChainChecks, CheckRes
from core.schains.monitor import RegularMonitor
from core.schains.config.generator import save_schain_config
from core.schains.config.helper import get_schain_config

from tools.configs import (
    SGX_CERTIFICATES_FOLDER,
    SGX_SERVER_URL
)

from web.models.schain import SChainRecord

from tests.dkg_utils import safe_run_dkg_mock


logger = logging.getLogger(__name__)


def alter_schain_config(schain_name: str, public_key: str) -> None:
    """
    Fix config to make skaled work with a single node (mine blocks, etc)
    """
    config = get_schain_config(schain_name)
    node = config['skaleConfig']['sChain']['nodes'][0]
    node['publicKey'] = public_key
    config['skaleConfig']['sChain']['nodes'] = [node]
    save_schain_config(config, schain_name)


class RegularMonitorMock(RegularMonitor):
    @RegularMonitor.monitor_block
    def dkg(self) -> None:
        return safe_run_dkg_mock(
            skale=self.skale,
            schain_name=self.name,
            node_id=self.node_config.id,
            sgx_key_name=self.node_config.sgx_key_name,
            rotation_id=self.rotation_id,
            schain_record=self.schain_record
        )


class SChainChecksMock(SChainChecks):
    @property
    def firewall_rules(self) -> CheckRes:
        return CheckRes(True)


def test_regular_monitor(schain_db, skale, node_config, skale_ima, dutils, ssl_folder,
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
    schain_checks = SChainChecksMock(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        dutils=dutils
    )
    test_monitor = RegularMonitorMock(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks,
        dutils=dutils
    )

    test_monitor.run()

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
