from core.config.mirage.generator import generate_mirage_config


def test_generate_mirage_config():
    nodes = []
    node_groups = {}
    schain_config = generate_mirage_config(nodes, node_groups)
    config = schain_config.to_dict()

    assert config['sChain']['schainID'] == 934
    # print(json.dumps(config, indent=4))
    # assert False
