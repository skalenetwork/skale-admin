import functools
import time

import pytest

from core.schains.task import run_tasks, Task

ITERATIONS = 10
SCHAINS_NUM = 10


class StopActionError(Exception):
    pass


def action(name):
    for i in range(ITERATIONS):
        time.sleep(2)
    raise StopActionError(f'Stopping {name}')


@pytest.mark.skip
def test_tasks():
    tasks = [
        Task(
            f'test-schain-{i}',
            functools.partial(action, name=f'test-schain-{i}'),
            i
        )
        for i in range(SCHAINS_NUM)
    ]
    run_tasks(tasks=tasks)
    time.sleep(3)
