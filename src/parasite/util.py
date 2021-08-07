from __future__ import annotations

from logging import getLogger
from timeit import default_timer as timer
from urlpath import URL as Url
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

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


def open_browser(url: Url):
    import webbrowser

    logger.info('Opening %s in browser.', url)
    webbrowser.open(str(url), new=2)


def code(path: Path):
    import subprocess

    cmd = [
        'code',
        str(path),
    ]
    logger.info('Running %s', ' '.join(cmd))
    subprocess.run(
        [
            'code',
            str(path),
        ],
        check=True,
    )
