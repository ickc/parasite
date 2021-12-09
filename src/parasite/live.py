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
from dataclasses import dataclass, field
from functools import partial
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from urlpath import URL as Url

from .apps import post_to_html, read_md_to_ast
from .config import Config as StaticConfig
from .util import TimeElapse

if TYPE_CHECKING:
    from typing import Sequence

    from .data import Page

logger = logging.getLogger(__name__)


def serve(
    host: str,
    port: int,
    directory: Path,
    url: Optional[Url] = None,
) -> None:
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
) -> None:
    import webbrowser

    full_url = str(f"http://{host}:{port}/{url}")
    logger.info("Opening %s in browser.", full_url)
    webbrowser.open(full_url, new=2)


def code(path: Path) -> None:
    import subprocess  # nosec

    cmd = [
        "code",
        str(path),
    ]
    logger.info("Running %s", " ".join(cmd))
    subprocess.run(  # nosec
        cmd,
        check=True,
    )


@dataclass
class Config(StaticConfig):
    """Configure live serving parameters.

    Args:
        watch: glob patterns of source files to be watched (relative to current directory)
        watch_open: if specified, open all pages that are currently watching.
        watch_code: if specified, open all sources that are currently watching in VSCode.
        serve: if specified, open a server and serve indefinitely.
        serve_host: the host to serve.
        serve_port: the port to serve.
        serve_open: if specified, open this relative url.
    """

    watch: List[str] = field(default_factory=list)
    watch_open: bool = False
    watch_code: bool = False
    serve: bool = False
    serve_host: str = "localhost"
    serve_port: int = 5500
    serve_open: Optional[Url] = None

    def make_page(config, page: Page) -> None:
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
        config,
        pages: List[Page],
    ) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        if TYPE_CHECKING:
            from watchdog.events import FileSystemEvent

        class PageEventHandler(FileSystemEventHandler):
            def __init__(
                self,
                config: Config,
                pages: List[Page],
            ):
                self.config = config
                self.pages = pages

            def on_modified(self, event: FileSystemEvent) -> None:
                path = event.src_path
                logger.info("%s %s. Updating...", path, event.event_type)
                for page in self.pages:
                    if str(page.path.absolute()) == path:
                        self.config.make_page(page)

        event_handler = PageEventHandler(config, pages)
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
        config,
        pages: List[Page],
    ) -> None:
        from livereload import Server

        server = Server()
        for page in pages:
            server.watch(str(page.path), partial(config.make_page, page))
        # always open with serve
        port = config.serve_port
        if config.watch_open:
            host = config.serve_host
            for page in pages:
                open_browser(host, port, page.url)
        server.serve(root=str(config.output_dir), port=port)

    def watch_pages(
        config,
        all_pages: Sequence[Page],
    ) -> None:
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
            config.observe_pages_with_serve(pages)
        else:
            config.observe_pages_without_serve(pages)

    def live(
        config,
        all_pages: Sequence[Page],
    ) -> None:
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
            config.watch_pages(all_pages)
