import logging
import queue
import random
import threading
import time

from typing import Callable, NamedTuple
from core.schains.process import ProcessReport

logger = logging.getLogger(__name__)


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 20
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 40

SKALED_PIPELINE_SLEEP = 2
CONFIG_PIPELINE_SLEEP = 3
STUCK_TIMEOUT = 60 * 60 * 2
SHUTDOWN_INTERVAL = 60 * 10


class Pipeline(NamedTuple):
    name: str
    job: Callable


# class Runner:
#     def __init__(
#         self,
#         pipelines: list[Pipeline],
#         reporting_queue: queue.Queue,
#         stuck_timeout: int = STUCK_TIMEOUT,
#         shutdown_interval: int = SHUTDOWN_INTERVAL
#     ) -> None:
#         self.pipelines = pipelines
#         self.reporting_queue = reporting_queue
#         self.stuck_timeout = stuck_timeout
#         self.shutdown_interval = shutdown_interval
#         self.number = len(pipelines)
#
#     def make_threads(self) -> None:
#         init_ts = time.time()
#         heartbeat_queues = [queue.Queue() for _ in range(self.number)]
#         terminating_events = [threading.Event() for _ in range(self.number)]
#         heartbeat_ts = [init_ts for _ in range(self.number)]
#
#         return [
#             threading.Thread(
#                 name=pipeline.name,
#                 target=keep_pipeline,
#                 args=[heartbeat_queue, terminating_event, pipeline.job],
#             )
#             for heartbeat_queue, terminating_event, pipeline in zip(
#                     heartbeat_queues, terminating_events, self.pipelines
#             )
#         ]
#
#     def run_threads(self, threads: list[threading.Thread]) -> None:
#         for th in threads:
#             th.start()
#
#     def run(self, once: bool = False) -> None:
#         threads = self.make_threads()
#         self.run_threads(threads)


def run_pipelines(
    pipelines: list[Pipeline],
    process_report: ProcessReport,
    once: bool = False,
    stuck_timeout: int = STUCK_TIMEOUT,
    shutdown_interval: int = SHUTDOWN_INTERVAL,
) -> None:
    init_ts = time.time()

    heartbeat_queues = [queue.Queue() for _ in range(len(pipelines))]
    terminating_events = [threading.Event() for _ in range(len(pipelines))]
    heartbeat_ts = [init_ts for _ in range(len(pipelines))]

    threads = [
        threading.Thread(
            name=pipeline.name,
            target=keep_pipeline,
            args=[heartbeat_queue, terminating_event, pipeline.job],
        )
        for heartbeat_queue, terminating_event, pipeline in zip(
            heartbeat_queues, terminating_events, pipelines
        )
    ]

    for th in threads:
        th.start()

    stuck = False
    while not stuck:
        for pindex, heartbeat_queue in enumerate(heartbeat_queues):
            if not heartbeat_queue.empty():
                heartbeat_ts[pindex] = heartbeat_queue.get()
            ts = int(time.time())
            if ts - heartbeat_ts[pindex] > stuck_timeout:
                logger.warning(
                    '%s pipeline has stucked (last heartbeat %d)',
                    pipelines[pindex].name,
                    heartbeat_ts[pindex],
                )
                stuck = True
                break
        if once and all((lambda ts: ts > init_ts, heartbeat_ts)):
            logger.info('Successfully completed requested single run')
            break
        ts = int(time.time())
        process_report.ts = ts

    logger.info('Terminating all pipelines')
    for event in terminating_events:
        if not event.is_set():
            event.set()
    if stuck:
        logger.info('Joining threads with timeout')
        for thread in threads:
            thread.join(timeout=shutdown_interval)
        process_report.ts = 0
        logger.warning('Stuck was detected')

    logger.info('Finishing with pipelines')


def keep_pipeline(
    reporting_queue: queue.Queue, terminate: threading.Event, pipeline: Callable
) -> None:
    while not terminate.is_set():
        logger.info('Running pipeline')
        try:
            pipeline()
        except Exception:
            logger.exception('Pipeline run failed')
            terminate.set()
        reporting_queue.put(time.time())
        sleep_for_a_while()


def sleep_for_a_while():
    schain_monitor_sleep = random.randint(
        MIN_SCHAIN_MONITOR_SLEEP_INTERVAL, MAX_SCHAIN_MONITOR_SLEEP_INTERVAL
    )
    logger.info('Monitor iteration completed, sleeping for %d', schain_monitor_sleep)
    time.sleep(schain_monitor_sleep)
