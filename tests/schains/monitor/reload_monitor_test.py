import logging
import platform
import time

import mock

from skale.schain_config.generator import get_nodes_for_schain
from skale.wallets import SgxWallet
from skale.utils.helper import ip_from_bytes

from core.schains.checks import SChainChecks
from core.schains.ima import ImaData
from core.schains.monitor import RegularMonitor, ReloadMonitor
from core.schains.runner import get_container_info

from tools.configs import (
    SGX_CERTIFICATES_FOLDER,
    SGX_SERVER_URL
)
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import SChainRecord

from tests.dkg_utils import safe_run_dkg_mock
from tests.utils import (
    alter_schain_config,
    get_test_rule_controller,
    no_schain_artifacts
)


logger = logging.getLogger(__name__)


def test_reload_monitor(
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
    reload_monitor = ReloadMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks,
        rule_controller=rc,
        dutils=dutils
    )
    regular_monitor = RegularMonitor(
        skale=skale,
        ima_data=ima_data,
        schain=schain,
        node_config=node_config,
        rotation_data={'rotation_id': 0},
        checks=schain_checks,
        rule_controller=rc,
        dutils=dutils
    )

    schain_record.set_needs_reload(True)

    with no_schain_artifacts(schain['name'], dutils):
        reload_monitor.config_dir()
        reload_monitor.run()

        schain_record = SChainRecord.get_by_name(schain_name)
        assert schain_record.needs_reload is False
        info = dutils.get_info(container_name)
        assert info['status'] == 'not_found'

        with mock.patch(
            'core.schains.monitor.base_monitor.safe_run_dkg',
            safe_run_dkg_mock
        ):
            regular_monitor.run()
        alter_schain_config(schain_name, sgx_wallet.public_key)

        state = dutils.get_info(container_name)['stats']['State']
        assert state['Status'] == 'running'
        initial_started_at = state['StartedAt']

        reload_monitor.run()

        state = dutils.get_info(container_name)['stats']['State']
        assert state['Status'] == 'running'
        assert state['StartedAt'] > initial_started_at

        assert schain_record.needs_reload is False
        assert schain_checks.config_dir.status
        assert schain_checks.dkg.status
        assert schain_checks.config.status
        assert schain_checks.volume.status
        assert schain_checks.skaled_container.status
        assert not schain_checks.ima_container.status

        time.sleep(5)

        if platform.system() != 'Darwin':  # not working due to the macOS networking in Docker  # noqa
            assert schain_checks.rpc.status
            assert schain_checks.blocks.status