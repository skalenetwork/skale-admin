import logging

from skale.schain_config.generator import get_nodes_for_schain
from skale.wallets import SgxWallet
from skale.utils.helper import ip_from_bytes

from core.schains.checks import SChainChecks
from core.schains.ima import ImaData
from core.schains.monitor import SyncNodeMonitor
from core.schains.runner import get_container_info

from tools.configs import (
    SGX_CERTIFICATES_FOLDER,
    SGX_SERVER_URL
)
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import SChainRecord

from tests.utils import get_test_rule_controller


logger = logging.getLogger(__name__)


def test_sync_node_monitor(
    schain_db,
    skale,
    node_config,
    skale_ima,
    dutils,
    ssl_folder,
    schain_on_contracts
):
    schain_name = schain_on_contracts
    schain = skale.schains.get_by_name(schain_name)
    nodes = get_nodes_for_schain(skale, schain_name)
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER,
        schain_db
    )

    # not using rule_controller fixture to avoid config generation
    rc = get_test_rule_controller(name=schain_name)

    sgx_wallet = SgxWallet(
        web3=skale.web3,
        sgx_endpoint=SGX_SERVER_URL,
        path_to_cert=SGX_CERTIFICATES_FOLDER
    )

    node_config.id = nodes[0]['id']
    node_config.ip = ip_from_bytes(nodes[0]['ip'])
    node_config.sgx_key_name = sgx_wallet.key_name

    schain_record = SChainRecord.get_by_name(schain_name)
    schain_record.set_needs_reload(True)

    schain_checks = SChainChecks(
        schain_name,
        node_config.id,
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils
    )
    ima_data = ImaData(False, '0x1')
    sync_node_monitor = SyncNodeMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain,
        node_config=node_config,
        rotation_data={'rotation_id': 0, 'leaving_node': 1},
        checks=schain_checks,
        rule_controller=rc,
        dutils=dutils
    )

    sync_node_monitor.run()

    assert schain_checks.config_dir.status
    assert schain_checks.config.status
    assert schain_checks.volume.status
    assert not schain_checks.ima_container.status
