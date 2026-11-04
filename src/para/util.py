from __future__ import annotations

import inspect
import logging
import os
from timeit import default_timer as timer


class Formatter(logging.Formatter):
    """Level names in colour on a terminal (not with NO_COLOR set)."""

    COLOURS = {"DEBUG": "36", "INFO": "32", "WARNING": "33", "ERROR": "31", "CRITICAL": "1;31"}

    def __init__(self, fmt: str, colour: bool = False) -> None:
        super().__init__(fmt)
        self.colour = colour

    def formatMessage(self, record: logging.LogRecord) -> str:
        if self.colour and (code := self.COLOURS.get(record.levelname)):
            record = logging.makeLogRecord({**record.__dict__, "levelname": f"\033[{code}m{record.levelname}\033[0m"})
        return super().formatMessage(record)


def _args(doc: str) -> tuple[list[str], list[str], list[str]]:
    """A Google-style docstring as (before its Args, the Args' lines, after them)."""
    lines = inspect.cleandoc(doc).splitlines()
    if "Args:" not in lines:
        return lines, [], []
    start = lines.index("Args:") + 1
    end = start
    while end < len(lines) and (not lines[end] or lines[end].startswith(" ")):
        end += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[: start - 1], lines[start:end], lines[end:]


def inherit_args(cls: type) -> type:
    """Prepend the Args of the base class's docstring to ``cls``'s, so that the command
    line's help (defopt) describes every field of a subclassed config."""
    _, inherited, _ = _args(cls.__bases__[0].__doc__ or "")
    before, own, after = _args(cls.__doc__ or "")
    cls.__doc__ = "\n".join([*before, "Args:", *inherited, *own, *after])
    return cls


def setup_logging(
    name: str = "para",
    level: str = "INFO",
    env_var: str = "PARASITELOGLEVEL",
    fmt: str = "%(name)s %(levelname)s %(message)s",
) -> logging.Logger:
    """Setup logging.

    :param env_var: if not empty, set log level from this environment variable.
    """
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(Formatter(fmt, colour=not os.environ.get("NO_COLOR") and handler.stream.isatty()))
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
