import os
import pathlib
import shutil
from typing import cast

import pytest
from skale.types.schain import SchainName
from skale_core.settings import get_settings

from core.checks.schain import SChainChecks
from tests.utils import CONFIG_STREAM, STATIC_NODE_GROUPS, get_random_string
from tools.constants import STATIC_GROUPS_FOLDER
from tools.constants.schains import SCHAINS_DIR_PATH
from tools.helper import write_json
from web.models.schain import SChainRecord


@pytest.fixture
def _schain_name() -> SchainName:
    """Generates default schain name"""
    return cast(SchainName, get_random_string())


@pytest.fixture
def _test_schain_name() -> SchainName:
    return SchainName('test_chain')


@pytest.fixture
def schain_checks(schain_config, schain_db, current_nodes, rule_controller, estate, dutils):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    return SChainChecks(
        schain_name,
        node_id,
        schain_record=schain_record,
        rule_controller=rule_controller,
        stream_version=CONFIG_STREAM,
        current_nodes=current_nodes,
        last_dkg_successful=True,
        estate=estate,
        dutils=dutils,
    )


@pytest.fixture
def schain_struct(schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    return {'name': schain_name, 'partOfNode': 0, 'generation': 0}


@pytest.fixture
def cleanup_schain_dirs_before():
    shutil.rmtree(SCHAINS_DIR_PATH, ignore_errors=True)
    pathlib.Path(SCHAINS_DIR_PATH).mkdir(parents=True, exist_ok=True)
    return


@pytest.fixture
def static_groups_for_schain(_schain_name):
    st = get_settings()
    parent_folder = os.path.join(STATIC_GROUPS_FOLDER, st.env_type)
    os.makedirs(parent_folder)
    static_groups_env_path = os.path.join(
        parent_folder, os.path.join(f'schain-{_schain_name}.json')
    )
    try:
        write_json(static_groups_env_path, STATIC_NODE_GROUPS)
        yield STATIC_NODE_GROUPS
    finally:
        shutil.rmtree(STATIC_GROUPS_FOLDER, ignore_errors=True)
