import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class Task:
    def __init__(
        self,
        name: str,
        action: Callable,
        index: int = 0,
        sleep: int = 2
    ) -> None:
        self.name = name
        self.index = index
        self.action = action
        self.sleep = sleep

    def run(self) -> None:
        try:
            self.action()
        except Exception as e:
            logger.exception('Task %s failed with %s', self.name, e)
        logger.info('Sleeping after task execution for %d', self.sleep)
        time.sleep(self.sleep)


def keep_tasks_running(
    executor: ThreadPoolExecutor,
    tasks: List[Task],
    futures: List[Optional[Future]]
) -> None:
    for i, task in enumerate(tasks):
        future = futures[i]
        if future is not None and not future.running():
            result = future.result()
            logger.info('Task %s finished with %s', task.name, result)
        if future is None or not future.running():
            logger.info('Running task %s', task.name)
            futures[i] = executor.submit(task.run)


def run_tasks(name: str, tasks: List[Task]) -> None:
    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix='T') as executor:
        futures: List[Optional[Future]] = [None for i in range(len(tasks))]
        while True:
            keep_tasks_running(executor, tasks, futures)
            time.sleep(30)
