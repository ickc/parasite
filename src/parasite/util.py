from __future__ import annotations

import logging
import os
from timeit import default_timer as timer

try:
    from coloredlogs import ColoredFormatter as Formatter
except ImportError:
    from logging import Formatter


def setup_logging(
    name: str = 'parasite',
    level: str = "INFO",
    env_var: str = "PARASITELOGLEVEL",
    fmt: str = "%(name)s %(levelname)s %(message)s",
    Handler=logging.StreamHandler,
    Formatter=Formatter,
) -> logging.Logger:
    """Setup logging.

    :param env_var: if not empty, set log level from this environment variable.
    """
    logger = logging.getLogger(name)
    handler = Handler()
    handler.setFormatter(Formatter(fmt))
    logger.addHandler(handler)
    if env_var:
        try:
            _level = os.environ.get(env_var, level)
            logger.setLevel(level=_level)
        except ValueError:
            logger.setLevel(level=level)
            logger.error('%s=%s is not a valid logging level, set to default %s.', env_var, _level, level)
    else:
        logger.setLevel(level=level)
    return logger


class TimeElapse:

    def __init__(self, logger=logging.getLogger(__name__)):
        self.time = timer()
        self.logger = logger

    def update(self):
        self.time = timer()

    def report(self, string):
        time_original = self.time
        self.update()
        self.logger.info(f'{self.time - time_original:.3f}s spent: {string}')
