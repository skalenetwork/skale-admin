import os

# N_OF_NODES = int(os.getenv('N_OF_NODES'))
TEST_ETH_AMOUNT = 1

SCHAIN_TYPE = os.getenv('SCHAIN_TYPE')
SCHAIN_TYPES = {
    'tiny': (16, 1),
    'test2': (2, 4),
    'test4': (4, 5)
}
N_OF_NODES = SCHAIN_TYPES[SCHAIN_TYPE][0]
TYPE_OF_NODES = SCHAIN_TYPES[SCHAIN_TYPE][1]
