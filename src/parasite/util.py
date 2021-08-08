from __future__ import annotations

from logging import getLogger
from timeit import default_timer as timer

logger = getLogger('parasite')


class TimeElapse:

    def __init__(self):
        self.time = timer()

    def update(self):
        self.time = timer()

    def report(self, string):
        time_original = self.time
        self.update()
        logger.info(f'{self.time - time_original:.3f}s spent: {string}')
