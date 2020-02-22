import logging
import time

from skale import Skale
from skale.wallets import RPCWallet

from core.node_config import NodeConfig
from core.schains.creator import run_creator
from core.schains.cleaner import run_cleaner

from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, TM_URL
from tools.logger import init_admin_monitor_logger


init_admin_monitor_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 50
MONITOR_INTERVAL = 45


def monitor(skale, node_config):
    while True:
        run_creator(skale, node_config)
        time.sleep(MONITOR_INTERVAL)
        run_cleaner(skale, node_config)
        time.sleep(MONITOR_INTERVAL)


def main():
    rpc_wallet = RPCWallet(TM_URL)
    skale = Skale(ENDPOINT, ABI_FILEPATH, rpc_wallet)
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    monitor(skale, node_config)


if __name__ == '__main__':
    main()
