from core.schains.config.generator import generate_schain_config


def test_generate_schain_config():
    schain_config = generate_schain_config()

    # print(schain_config)
    print(schain_config.to_dict())
    assert False
