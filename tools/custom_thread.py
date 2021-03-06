#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import threading
import logging

logger = logging.getLogger(__name__)


class CustomThread(threading.Thread):

    def __init__(self, name, func, opts=None, interval=1.0, once=False):
        """ Setting initial variables """
        self._stopevent = threading.Event()
        self._sleepperiod = interval
        self.func = func
        self.opts = opts
        self.once = once

        threading.Thread.__init__(self, name=name)

    def run(self):
        """ Main control loop """
        logger.debug(f'{self.getName()} thread starts')

        if self.once:
            self.safe_run_func()
        else:
            running_counter = 0
            while not self._stopevent.isSet():
                logger.info(f'Running function from thread '
                            f'{self.getName()}, try: {running_counter}')
                self.safe_run_func()
                self._stopevent.wait(self._sleepperiod)
                running_counter += 1

        logger.debug(f'{self.getName()} thread ends')

    def safe_run_func(self):
        try:
            self.func(self.opts)
        except Exception as err:
            logger.exception(
                f'Error was occurred during the execution. Function: {self.func.__name__}. '
                f'Error {err}.')
            # raise e todo: handle

    def join(self, timeout=None):
        """ Stop the thread. """
        self._stopevent.set()
        threading.Thread.join(self, timeout)


def test(opts):
    print(12345)


if __name__ == "__main__":
    testthread = CustomThread('test', test)
    testthread.start()

    import time

    time.sleep(10.0)

    testthread.join()
