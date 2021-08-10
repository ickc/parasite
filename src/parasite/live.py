"""This handle the following config specific to live events:

watch
watch_open
watch_code
serve
serve_host
serve_port
serve_open
"""

from __future__ import annotations

import logging
from functools import partial
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from urlpath import URL as Url

from .apps import post_to_html, read_md_to_ast
from .util import TimeElapse

if TYPE_CHECKING:
    from typing import List, Optional, Sequence

    from .config import Config
    from .data import Page

logger = logging.getLogger(__name__)


def serve(
    host: str,
    port: int,
    directory: Path,
    url: Optional[Url] = None,
):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    from threading import Thread

    httpd = HTTPServer(
        (host, port),
        partial(SimpleHTTPRequestHandler, directory=directory),
    )
    Thread(target=httpd.serve_forever).start()
    logger.info("Serving at port %s.", port)
    # always open with serve
    if url is not None:
        open_browser(host, port, url)


def open_browser(
    host: str,
    port: int,
    url: Url = Url(""),
):
    import webbrowser

    full_url = str(f"http://{host}:{port}/{url}")
    logger.info("Opening %s in browser.", full_url)
    webbrowser.open(full_url, new=2)


def code(path: Path):
    import subprocess

    cmd = [
        "code",
        str(path),
    ]
    logger.info("Running %s", " ".join(cmd))
    subprocess.run(
        [
            "code",
            str(path),
        ],
        check=True,
    )


def _make_single_page(page: Page, config: Config):
    time_elapse = TimeElapse(logger)
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
    time_elapse.report(f"{page.path} redone.")


def observe_pages_without_serve(
    pages: List[Page],
    config: Config,
):
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class PageEventHandler(FileSystemEventHandler):
        def __init__(self, pages: List[Page], config: Config):
            self.pages = pages
            self.config = config

        def on_modified(self, event):
            path = event.src_path
            logger.info("%s %s. Updating...", path, event.event_type)
            for page in self.pages:
                if str(page.path.absolute()) == path:
                    _make_single_page(page, self.config)

    event_handler = PageEventHandler(pages, config)
    observer = Observer()
    for page in pages:
        path = page.path
        observer.schedule(event_handler, path, recursive=True)
        logger.info("Watching %s", path)
    try:
        observer.start()
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()


def observe_pages_with_serve(
    pages: List[Page],
    config: Config,
):
    from livereload import Server

    server = Server()
    for page in pages:
        server.watch(str(page.path), partial(_make_single_page, page, config))
    # always open with serve
    port = config.serve_port
    if config.watch_open:
        host = config.serve_host
        for page in pages:
            open_browser(host, port, page.url)
    server.serve(root=str(config.output_dir), port=port)


def watch_pages(
    all_pages: Sequence[Page],
    config: Config,
):
    """Watch and re-render single page."""
    globs = config.watch
    time_elapse = TimeElapse(logger)

    cur_dir = Path(".")
    paths = list(chain.from_iterable(cur_dir.glob(glob) for glob in globs))
    time_elapse.report(f"Found {len(paths)} paths to watch.")
    logger.debug("Watching the following paths: %s", paths)

    # get page with url
    pages: List[Page] = []
    for path in paths:
        page: Optional[Page] = None
        for cur_page in all_pages:
            if cur_page.path == path:
                page = cur_page
                break
        if page is None:
            raise ValueError(f"Cannot find page/post with path {path}")
        else:
            pages.append(page)
    time_elapse.report(f"Found {len(pages)} pages.")
    if config.watch_code:
        for page in pages:
            code(config.output_dir / page.out_path)
    if config.serve:
        observe_pages_with_serve(pages, config)
    else:
        observe_pages_without_serve(pages, config)


def live(
    all_pages: Sequence[Page],
    config: Config,
):
    """Go live."""
    # only serve ourselves if not watching
    if config.serve and not config.watch:
        serve(
            config.serve_host,
            config.serve_port,
            config.output_dir,
            url=config.serve_open,
        )
    # let watch_pages handle serve cases
    if config.watch:
        watch_pages(
            all_pages,
            config,
        )
