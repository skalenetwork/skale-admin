import os
import mock
from core.filebeat import filebeat_config_processed
from tools.configs.filebeat import NODE_DATA_PATH


PROCESSED_FILEBEAT_CONFIG_PATH = os.path.join(NODE_DATA_PATH, 'filebeat_processed.yml')


def test_filebeat_config_processed():
    assert not filebeat_config_processed()
    with mock.patch('core.filebeat.FILEBEAT_CONFIG_PATH', PROCESSED_FILEBEAT_CONFIG_PATH):
        assert filebeat_config_processed()
