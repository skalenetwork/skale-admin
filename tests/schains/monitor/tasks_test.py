import time
from core.schains.monitor.tasks import start_tasks


def test_tasks():
    start_tasks('test-chain')
    time.sleep(60)
