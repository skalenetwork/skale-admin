import json
from core.schains.config.generator import generate_schain_config


def test_generate_schain_config():
    schain_config = generate_schain_config()

    # print(schain_config)
    print(json.dumps(schain_config.to_dict(), indent=2))
    assert False
