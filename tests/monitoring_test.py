import json
import os

import pytest

from core.monitoring import TelegrafNotConfiguredError, update_telegraf_service
from tools.configs import DOCKER_NODE_CONFIG_FILEPATH
from tools.configs.monitoring import TELEGRAF_TEMPLATE_PATH, TELEGRAF_CONFIG_PATH


CONFIG_TEMPLATE = """
[agent]
  interval = "60s"
  hostname = "{{ ip }}"
  omit_hostname = false

[global_tags]
  node_id = "{{ node_id }}"

[[outputs.db]]
  alias = "db"
  urls = ["{{ url }}"]

"""

DOCKER_GROUP_ID = 1023


@pytest.fixture
def cleanup_container(dutils):
    try:
        yield
    finally:
        dutils.safe_rm('skale_telegraf')


@pytest.fixture
def telegraf_template():
    try:
        with open(TELEGRAF_TEMPLATE_PATH, 'w') as template:
            template.write(CONFIG_TEMPLATE)
        yield TELEGRAF_TEMPLATE_PATH
    finally:
        os.remove(TELEGRAF_TEMPLATE_PATH)
        os.remove(TELEGRAF_CONFIG_PATH)


@pytest.fixture
def docker_node_config():
    try:
        with open(DOCKER_NODE_CONFIG_FILEPATH, 'w') as docker_config:
            json.dump({'docker_group_id': DOCKER_GROUP_ID}, docker_config)
        yield DOCKER_NODE_CONFIG_FILEPATH
    finally:
        os.remove(DOCKER_NODE_CONFIG_FILEPATH)


def test_update_telegraf_service(docker_node_config, telegraf_template, cleanup_container, dutils):
    node_id = 1
    node_ip = '1.1.1.1'
    with pytest.raises(TelegrafNotConfiguredError):
        update_telegraf_service(
            node_id=node_id, node_ip='', url='http://127.0.0.1:1231', dutils=dutils
        )

    update_telegraf_service(node_ip, node_id, url='http://127.0.0.1:1231', dutils=dutils)
    with open(TELEGRAF_CONFIG_PATH) as config:
        config = config.read()
        assert (
            config == '\n[agent]\n  interval = "60s"\n  hostname = "1.1.1.1"\n  omit_hostname = false\n\n[global_tags]\n  node_id = "1"\n\n[[outputs.db]]\n  alias = "db"\n  urls = ["http://127.0.0.1:1231"]\n')  # noqa
    assert dutils.is_container_running('skale_telegraf')
    user_info = dutils.get_info('skale_telegraf')['stats']['Config']['User']
    assert user_info == f'telegraf:{DOCKER_GROUP_ID}'
