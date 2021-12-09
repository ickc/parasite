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
from importlib import import_module, reload
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from urlpath import URL as Url

from .apps import post_to_html, read_md_to_ast
from .config import Config as StaticConfig
from .util import TimeElapse

if TYPE_CHECKING:
    from threading import Thread
    from typing import Sequence

    from .data import Page

logger = logging.getLogger(__name__)


def serving(
    host: str,
    port: int,
    directory: Path,
    url: Optional[Url] = None,
) -> Thread:
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    from threading import Thread

    httpd = HTTPServer(
        (host, port),
        partial(SimpleHTTPRequestHandler, directory=directory),
    )
    thread = Thread(target=httpd.serve_forever)
    thread.start()
    logger.info("Serving simple server at port %s.", port)
    # always open with serve
    if url is not None:
        open_browser(host, port, url)
    return thread


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
        watch_module: if specified, watch & reload this module.
        serve: if specified, open a server and serve indefinitely.
        serve_host: the host to serve.
        serve_port: the port to serve.
        serve_open: if specified, open this relative url.
    """

    watch: List[str] = field(default_factory=list)
    watch_open: bool = False
    watch_code: bool = False
    watch_module: list[str] = field(default_factory=list)
    serve: bool = False
    serve_host: str = "localhost"
    serve_port: int = 5500
    serve_open: Optional[Url] = None

    def serving(self) -> Thread:
        return serving(
            self.serve_host,
            self.serve_port,
            self.output_dir,
            url=self.serve_open,
        )

    def make_page(self, page: Page) -> None:
        time_elapse = TimeElapse(logger)
        page.ast = read_md_to_ast(
            self.pandoc_input_options,
            self.panflute_input_filters,
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
            outputs=[self.output_dir / page.out_path],
            **page.options,
        )
        time_elapse.report(f"{page.path} redone.")

    def observe_pages_without_serve(
        self,
        pages: List[Page],
    ) -> None:
        """Watch using watchdog which is observer based."""
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
                self.modules = [import_module(m) for m in config.watch_module]

            def on_modified(self, event: FileSystemEvent) -> None:
                path = event.src_path
                logger.info("%s %s. Updating...", path, event.event_type)
                for module in self.modules:
                    logger.info("Reloading module %s", module)
                    reload(module)
                for page in self.pages:
                    if str(page.path.absolute()) == path:
                        self.config.make_page(page)

        event_handler = PageEventHandler(self, pages)
        observer = Observer()
        for page in pages:
            path = page.path
            observer.schedule(event_handler, path, recursive=True)
            logger.info("Watching %s", path)
        logger.info("Observing using watchdog without serving...")
        try:
            observer.start()
        except KeyboardInterrupt:
            observer.stop()
        finally:
            observer.join()

    def observe_pages_with_serve(
        self,
        pages: List[Page],
    ) -> None:
        """Watch using livereload which is polling based."""
        from livereload import Server

        server = Server()
        for page in pages:
            server.watch(str(page.path), partial(self.make_page, page))
        # always open with serve
        port = self.serve_port
        if self.watch_open:
            host = self.serve_host
            for page in pages:
                open_browser(host, port, page.url)
        logger.info("Observing and serving using livereload...")
        server.serve(root=str(self.output_dir), port=port)

    def watch_pages(
        self,
        all_pages: Sequence[Page],
    ) -> None:
        """Watch and re-render pages."""
        globs = self.watch
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
        if self.watch_code:
            for page in pages:
                code(self.output_dir / page.out_path)
        if self.serve:
            self.observe_pages_with_serve(pages)
        else:
            self.observe_pages_without_serve(pages)

    def live(
        self,
        all_pages: Sequence[Page],
    ) -> None:
        """Go live."""
        # only serve ourselves if not watching
        if self.serve and not self.watch:
            self.serving()
        # let watch_pages handle serve cases
        if self.watch:
            self.watch_pages(all_pages)
