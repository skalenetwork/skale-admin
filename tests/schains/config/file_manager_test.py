import json
import os
import shutil

import pytest

from core.schains.config.directory import schain_config_dir
from core.schains.config.file_manager import ConfigFileManager

from tools.configs.schains import SCHAINS_DIR_PATH


def test_config_file_manager(schain_db, schain_config, upstreams):
    name = schain_db
    cfm = ConfigFileManager(schain_name=name)
    assert cfm.skaled_config_path == os.path.join(
        SCHAINS_DIR_PATH,
        name,
        f'schain_{name}.json'
    )
    assert cfm.latest_upstream_path == os.path.join(
        schain_config_dir(name),
        f'schain_{name}_11_1687183339.json'
    )
