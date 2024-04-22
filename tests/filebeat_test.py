import os
import mock
from core.monitoring import filebeat_config_processed
from tools.configs.monitoring import NODE_DATA_PATH


PROCESSED_FILEBEAT_CONFIG_PATH = os.path.join(NODE_DATA_PATH, 'filebeat_processed.yml')


def test_filebeat_config_processed():
    assert not filebeat_config_processed()
    with mock.patch('core.filebeat.FILEBEAT_CONFIG_PATH', PROCESSED_FILEBEAT_CONFIG_PATH):
        assert filebeat_config_processed()
