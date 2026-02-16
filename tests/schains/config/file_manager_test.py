import os

from core.config.schain.directory import schain_config_dir
from core.config.schain.file_manager import ConfigFileManager
from tools.constants.schains import SCHAINS_DIR_PATH


def test_config_file_manager(schain_db, schain_config, upstreams):
    name = schain_db
    cfm = ConfigFileManager(chain_name=name)
    assert cfm.skaled_config_path == os.path.join(SCHAINS_DIR_PATH, name, f'schain_{name}.json')
    assert cfm.latest_upstream_path == os.path.join(
        schain_config_dir(name), f'schain_{name}_11_1687183339.json'
    )
