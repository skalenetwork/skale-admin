import functools
from filelock import FileLock

from tools.helper import read_json, write_json, init_file
from tools.configs import NODE_CONFIG_FILEPATH, NODE_CONFIG_LOCK_PATH


def config_setter(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        field_name, field_value = func(*args, **kwargs)
        lock = FileLock(NODE_CONFIG_LOCK_PATH)
        with lock:
            config = read_json(NODE_CONFIG_FILEPATH)
            config[field_name] = field_value
            write_json(NODE_CONFIG_FILEPATH, config)
    return wrapper_decorator


def config_getter(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        field_name = func(*args, **kwargs)
        config = read_json(NODE_CONFIG_FILEPATH)
        return config.get(field_name)
    return wrapper_decorator


class NodeConfig:
    def __init__(self):
        init_file(NODE_CONFIG_FILEPATH, {})

    @property
    @config_getter
    def id(self) -> int:
        return 'node_id'

    @id.setter
    @config_setter
    def id(self, node_id: int) -> None:
        return 'node_id', node_id

    @property
    @config_getter
    def ip(self) -> str:
        return 'node_ip'

    @ip.setter
    @config_setter
    def ip(self, ip: str) -> None:
        return 'node_ip', ip

    @property
    @config_getter
    def name(self) -> str:
        return 'name'

    @name.setter
    @config_setter
    def name(self, node_name: str) -> None:
        return 'name', node_name

    @property
    @config_getter
    def sgx_key_name(self) -> int:
        return 'sgx_key_name'

    @sgx_key_name.setter
    @config_setter
    def sgx_key_name(self, sgx_key_name: int) -> None:
        return 'sgx_key_name', sgx_key_name

    def all(self) -> dict:
        return read_json(NODE_CONFIG_FILEPATH)
