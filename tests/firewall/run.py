import concurrent.futures
import random
import subprocess
import time
import uuid
from tools.iptables import add_rules, has_rules, remove_rules

THREADS_NUMBER = 5


def test_add_rules():
    add_rules()
    pass

def run_in_threads():
    pass


if __name__ == '__main__':
    # run_iptables('12.12.12.12', 6543, 'foo')
    main()
