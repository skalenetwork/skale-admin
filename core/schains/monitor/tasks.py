import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

logger = logging.getLogger(__name__)


class Task:
    def __init__(
        self,
        schain: str,
        name: str,
        action: Callable,
        index: int,
        *args,
        **kwargs
    ) -> None:
        self.schain = schain
        self.name = name
        self.action = action
        self.index = index
        self.args = args
        self.kwargs = kwargs

    @property
    def signature(self) -> str:
        return f'[{self.schain}-{self.name}]'

    def run(self):
        self.action(*self.args, **self.kwargs)


def ensure_tasks(executor, tasks, futures):
    for i, task in enumerate(tasks):
        f = futures[i]
        if f is not None and not f.running():
            result = f.result()
            logger.info('Task %s finished with %s', task.signature, result)
        if f is None or not f.running():
            logger.info('Launching task %s', task.signature)
            futures[i] = executor.submit(task.run())


def start_tasks(schain: str):
    logger.info('Starting schain %s tasks', schain)
    tasks = [
        Task(schain, 'config-task', monitor_chain, 0),
        Task(schain, 'skaled-task', monitor_chain, 1),
    ]
    futures = [None for i in range(len(tasks))]
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        while True:
            ensure_tasks(executor, tasks, futures)


def monitor_chain():
    for i in range(50):
        if i % 5 == 0:
            logger.info('Monitoring chain %d', i)
        time.sleep(2)


def monitor_config():
    pass


def monitor_skaled():
    pass
