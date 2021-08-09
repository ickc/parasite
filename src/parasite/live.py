"""This handle the following config specific to live events:

watch_single_page
serve
open
code
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging
from functools import partial

from .apps import post_to_html, read_md_to_ast
from .util import TimeElapse

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Optional, List

    from urlpath import URL as Url

    from .data import Page
    from .config import Config

logger = logging.getLogger(__name__)


def serve(port: int, directory: Path):
    from threading import Thread
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    httpd = HTTPServer(('localhost', port), partial(SimpleHTTPRequestHandler, directory=directory))
    logger.info('Serving at port %s.', port)
    Thread(target=httpd.serve_forever).start()


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


def _make_single_page(page: Page, config: Config):
    time_elapse = TimeElapse()

    url = config.watch_single_page

    page.ast = read_md_to_ast(
        config.pandoc_input_options,
        config.panflute_input_filters,
        inputs=[page.path],
    )
    post_to_html(
        page.ast,
        page.root,
        page.prev,
        page.next,
        page.lang,
        page.ext,
        inputs=[] if page.template is None else [page.template],
        outputs=[config.output_dir / page.out_path],
        **page.options,
    )
    time_elapse.report(f'{url} redone.')


def observe_single_page_no_serve(
    page: Page,
    config: Config,
):
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class PageEventHandler(FileSystemEventHandler):

        def __init__(self, page: Page, config: Config):
            self.page = page
            self.config = config

            logger.info('Watching %s', page.path)

        def on_modified(self, event):
            logger.info('%s %s. Updating...', event.src_path, event.event_type)
            _make_single_page(self.page, self.config)

    path = page.path.resolve()

    event_handler = PageEventHandler(page, config)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    try:
        observer.start()
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()


def observe_single_page_serve(
    page: Page,
    config: Config,
):
    from livereload import Server

    server = Server()
    server.watch(str(page.path), partial(_make_single_page, page, config))
    # always open with serve
    if config.open is not None:
        open_browser(config.open)
    server.serve(root=str(config.output_dir), port=config.serve)


def watch_single_page(
    all_pages: List[Page],
    config: Config,
):
    """Watch and re-render single page."""
    url = config.watch_single_page
    time_elapse = TimeElapse()

    # get page with url
    page: Optional[Page] = None
    for cur_page in all_pages:
        if cur_page.url == url:
            page = cur_page
            break
    if page is None:
        raise ValueError(f'Cannot find page/post with url {url}')
    else:
        time_elapse.report(f'Found file at path {page.path}')
    if config.code:
        code(config.output_dir / page.out_path)
    if config.serve is None:
        observe_single_page_no_serve(page, config)
    else:
        observe_single_page_serve(page, config)


def live(
    all_pages: List[Page],
    config: Config,
):
    """Go live."""
    # only serve ourselves if not watching
    if config.serve is not None and config.watch_single_page is None:
        serve(config.serve, config.output_dir)
        # always open with serve
        if config.open is not None:
            open_browser(config.open)
    # let watch_single_page handle serve cases
    if config.watch_single_page is not None:
        watch_single_page(
            all_pages,
            config,
        )
