#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from threading import Thread
from time import sleep

logger = logging.getLogger(__name__)


class Poller():
    def __init__(self, func, poll_interval, opts=None):
        logger.info(f'adding poller: {func.__name__}, poll_interval: {poll_interval}')
        self.poll_interval = poll_interval
        self.func = func
        self.opts = opts
        self.stopped = False

    def loop(self):
        while not self.stopped:
            try:
                self.func(self.opts)
                sleep(self.poll_interval)
            except Exception as e:
                logger.exception(f'Error was occurred during the function execution: {self.func.__name__}. See full stacktrace below.')
                #raise e todo: handle

    def run(self):
        logger.info(f'run poller: {self.func.__name__}, poll_interval: {self.poll_interval}')
        self.stopped = False
        self.worker = Thread(target=self.loop)
        self.worker.start()

    def stop(self, timeout=10):
        self.stopped = True
        self.worker.join(timeout)
