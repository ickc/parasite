from __future__ import annotations

import logging
import os
from timeit import default_timer as timer

try:
    from coloredlogs import ColoredFormatter as Formatter
except ImportError:
    from logging import Formatter


def setup_logging(
    name: str = "para",
    level: str = "INFO",
    env_var: str = "PARASITELOGLEVEL",
    fmt: str = "%(name)s %(levelname)s %(message)s",
    Handler: type[logging.StreamHandler] = logging.StreamHandler,  # type: ignore[type-arg]
    Formatter: type[Formatter] = Formatter,
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
            logger.error(
                "%s=%s is not a valid logging level, set to default %s.",
                env_var,
                _level,
                level,
            )
    else:
        logger.setLevel(level=level)
    return logger


class TimeElapse:
    def __init__(self, logger: logging.Logger = logging.getLogger(__name__)) -> None:
        self.time = timer()
        self.logger = logger

    def update(self) -> None:
        self.time = timer()

    def report(self, string: str) -> None:
        time_original = self.time
        self.update()
        self.logger.info(f"{self.time - time_original:.3f}s spent: {string}")


def join_url(root: str, url: str) -> str:
    """``url`` (relative to the site's root) from a page whose root is ``root`` (``..``,
    ``../..``, or ``.`` at the top)."""
    import posixpath

    return url if root in ("", ".") else posixpath.join(root, url)
