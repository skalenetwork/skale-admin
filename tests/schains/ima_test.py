from core.ima.container import get_ima_env
from web.models.schain import SChainRecord


def test_get_ima_env(schain_db, schain_config):
    ima_env = get_ima_env(schain_name=schain_db, mainnet_chain_id=123, time_frame=100)
    ima_env_dict = ima_env.to_dict()
    assert len(ima_env_dict) == 23
    assert ima_env_dict['CID_MAIN_NET'] == 123
    assert ima_env_dict['RPC_PORT'] == 10010
    assert ima_env_dict['TIME_FRAMING'] == 100
    assert isinstance(ima_env_dict['CID_SCHAIN'], str)
    assert ima_env_dict['SCHAIN_RPC_URL'] == 'http://127.0.0.1:10003'

    SChainRecord.get_by_name(schain_db).set_rpc_proxy_mode(True)
    proxied_env = get_ima_env(schain_name=schain_db, mainnet_chain_id=123, time_frame=100)
    assert proxied_env.to_dict()['SCHAIN_RPC_URL'] == 'http://127.0.0.1:10035'
