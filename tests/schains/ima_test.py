from core.schains.ima import get_ima_env


def test_get_ima_env(_schain_name, schain_config):
    ima_env = get_ima_env(
        schain_name=_schain_name,
        mainnet_chain_id=123
    )
    ima_env_dict = ima_env.to_dict()
    assert len(ima_env_dict) == 22
    assert ima_env_dict['CID_MAIN_NET'] == 123
    assert ima_env_dict['RPC_PORT'] == 10010
    isinstance(ima_env_dict['CID_SCHAIN'], str)
