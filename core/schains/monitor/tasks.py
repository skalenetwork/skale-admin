import abc
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from core.schains.process import ProcessReport


logger = logging.getLogger(__name__)


SLEEP_INTERVAL = 10


class ITask(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def stuck_timeout(self) -> int:
        pass

    @abc.abstractmethod
    def create_pipeline(self) -> Callable:
        pass

    @property
    @abc.abstractmethod
    def future(self) -> Future:
        pass

    @future.setter
    @abc.abstractmethod
    def future(self, value: Future) -> None:
        pass

    @property
    def needed(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def start_ts(self) -> int:
        pass

    @start_ts.setter
    @abc.abstractmethod
    def start_ts(self, value: int) -> None:
        pass


def execute_tasks(
    tasks: list[ITask],
    process_report: ProcessReport,
    sleep_interval: int = SLEEP_INTERVAL,
) -> None:
    logger.info('Running tasks %s', tasks)
    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix='T') as executor:
        stucked = []
        while True:
            for index, task in enumerate(tasks):
                if not task.future.running() and task.needed:
                    task.start_ts = int(time.time())
                    logger.info('Starting task %s at %d', task.name, task.start_ts)
                    pipeline = task.create_pipeline()
                    task.future = executor.submit(pipeline)
                elif task.future.running():
                    if int(time.time()) - task.start_ts > task.stuck_timeout:
                        logger.info('Canceling future for %s', task.name)
                        canceled = task.future.cancel()
                        if not canceled:
                            logger.warning('Stuck detected for job %s', task.name)
                            task.start_ts = -1
                            stucked.append(task.name)
            time.sleep(sleep_interval)
            if len(stucked) > 0:
                logger.info('Sleeping before subverting execution')
                executor.shutdown(wait=False)
                logger.info('Subverting execution. Stucked %s', stucked)
                process_report.ts = 0
                break
            process_report.ts = int(time.time())
