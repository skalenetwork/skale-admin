from admin import main as l2_active_main
from skale_passive import main as l2_passive_main
from tools.configs import PASSIVE_NODE


if __name__ == '__main__':
    if PASSIVE_NODE:
        l2_passive_main()
    else:
        l2_active_main()
