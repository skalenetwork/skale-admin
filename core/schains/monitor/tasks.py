import abc
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, NamedTuple

from core.schains.process import ProcessReport


logger = logging.getLogger(__name__)


STUCK_TIMEOUT = 60 * 60 * 2
SHUTDOWN_INTERVAL = 60 * 10


class Pipeline(NamedTuple):
    name: str
    job: Callable


class ITaskBuilder(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def task_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def stuck_timeout(self) -> int:
        pass

    @abc.abstractmethod
    def build_task(self) -> Callable:
        pass


def test_job1():
    for i in range(500):
        if i % 3 == 1:
            print('Job 1 OOO')
        time.sleep(1)


def test_job2():
    for i in range(500):
        if i % 3 == 1:
            print('Job 2 YYY')
        time.sleep(1)


class TestPipelineBuilder1:
    def __init__(self) -> None:
        self._task_name = 'task2'
        self._stuck_timeout = 5

    @property
    def task_name(self) -> str:
        return self._task_name

    @property
    def stuck_timeout(self) -> str:
        return self._stuck_timeout

    def build_task(self):
        return [
            Pipeline(name='test0', job=test_job1()),
        ]


class TestPipelineBuilder2:
    def __init__(self) -> None:
        self.task_name = 'task2'
        self.stuck_timeout = 5

    def build_task(self):
        return [
            Pipeline(name='test1', job=test_job2()),
        ]


class StuckMonitorError(Exception):
    pass


def execute_tasks(
    task_builders: list[ITaskBuilder],
    process_report: ProcessReport,
    once: bool = False,
    shutdown_interval: int = SHUTDOWN_INTERVAL,
) -> None:
    with ThreadPoolExecutor(max_workers=len(task_builders), thread_name_prefix='mon_') as executor:
        stucked = []
        futures = [Future() for _ in task_builders]
        start_ts = [0 for _ in task_builders]
        while True:
            for index, builder in enumerate(task_builders):
                if not futures[index].running():
                    job = builder.build_task()
                    start_ts[index] = int(time.time())
                    futures[index] = executor.submit(job)
                else:
                    if time.time() - start_ts[index] > builder.stuck_timeout:
                        canceled = futures[index].cancel()
                        if not canceled:
                            logger.warning('Stuck detected for job {builder.name}')
                            stucked.append(builder.name)

            logger.info('Sleeping before stopping executor')
            time.sleep(shutdown_interval)

            if len(stucked) > 0:
                executor.shutdown(wait=False)
                logger.info('Subverting execution. Stucked %s', stucked)
                process_report.ts = 0
                break
            if once:
                break
            process_report.ts = int(time.time())
