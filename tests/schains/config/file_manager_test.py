import json
import os
import shutil

import pytest

from core.schains.config.directory import schain_config_dir
from core.schains.config.filename import ConfigFileManager

from tools.configs.schains import SCHAINS_DIR_PATH


@pytest.fixture
def upstreams2(schain_db, schain_config):
    name = schain_db
    config_folder = schain_config_dir(name)
    files = [
        f'schain_{name}_10_1687183338.json',
        f'schain_{name}_9_1687183335.json',
        f'schain_{name}_11_1687183336.json',
        f'schain_{name}_11_1687183337.json',
        f'schain_{name}_11_1687183339.json'
    ]
    try:
        for fname in files:
            fpath = os.path.join(config_folder, fname)
            with open(fpath, 'w') as f:
                json.dump(schain_config, f)
        yield files
    finally:
        shutil.rmtree(config_folder)


def test_config_file_manager(schain_db, schain_config, upstreams2):
    name = schain_db
    cfm = ConfigFileManager(schain_name=name)
    assert cfm.skaled_config_path == os.path.join(
        SCHAINS_DIR_PATH,
        name,
        f'schain_{name}.json'
    )
    assert cfm.latest_upstream_path == os.path.join(
        schain_config_dir(name),
        f'schain_{name}_11_9333817861.json'
    )
