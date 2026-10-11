"""This handle live events.
"""

from __future__ import annotations

import io
import json
import logging
import time
from dataclasses import dataclass, field
from functools import cached_property, partial
from importlib import import_module, reload
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional


import panflute as pf

from .apps import post_to_html, read_md_to_ast
from .data import format_years, root_of
from .config import Config as StaticConfig
from .util import TimeElapse

if TYPE_CHECKING:
    from http.server import ThreadingHTTPServer
    from types import ModuleType
    from typing import Sequence

    from .data import Page

logger = logging.getLogger(__name__)


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


def path_to_page(pages: list[Page]) -> dict[str, Page]:
    return {str(page.path.absolute()): page for page in pages}


@dataclass
class Config(StaticConfig):
    """Configure live serving parameters.

    Args:
        watch: glob patterns of source files to be watched (relative to current directory)
        watch_open: if specified, open all pages that are currently watching.
        watch_code: if specified, open all sources that are currently watching in VSCode.
        watch_module: if specified, watch & reload this module.
        serve: if specified, open a server and serve indefinitely.
        watch_with: valid choices are livereload, watchdog. If not specified, default to livereload if serve, else watchdog.
        serve_host: the host to serve.
        serve_port: the port to serve.
        serve_open: if specified, open this relative url.
    """

    watch: List[str] = field(default_factory=list)
    watch_open: bool = False
    watch_code: bool = False
    watch_module: list[str] = field(default_factory=list)
    serve: bool = False
    watch_with: str = ""
    serve_host: str = "localhost"
    serve_port: int = 5500
    serve_open: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.watch_with:
            self.watch_with = "livereload" if self.serve else "watchdog"
            logger.info("Defaulting watch_with as %s", self.watch_with)

    @cached_property
    def modules_to_be_watched(self) -> dict[str, ModuleType]:
        return {
            (module := import_module(name)).__file__: module  # type: ignore[misc]
            for name in self.watch_module
        }

    @cached_property
    def serving(self) -> ThreadingHTTPServer:
        host = self.serve_host
        port = self.serve_port
        directory = self.output_dir

        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        httpd = ThreadingHTTPServer(
            (host, port),
            partial(SimpleHTTPRequestHandler, directory=directory),
        )
        logger.info("Serving simple server at port %s.", port)
        return httpd

    def open_browser(self, url: str) -> None:
        host = self.serve_host
        port = self.serve_port

        import webbrowser

        full_url = str(f"http://{host}:{port}/{url}")
        logger.info("Opening %s in browser.", full_url)
        webbrowser.open(full_url, new=2)

    def make_page(self, page: Page) -> None:
        """Read ``page`` and render its outputs (a live rebuild: its own years only)."""
        time_elapse = TimeElapse(logger)
        page.ast = read_md_to_ast(
            self.pandoc_input_options,
            self.panflute_input_filters,
            inputs=[page.path],
            **self.media_options(page),
        )
        page.set_profiles()
        outputs = page.outputs
        for i, (profile, out_path) in enumerate(outputs):
            ast = page.ast if i == len(outputs) - 1 else pf.load(io.StringIO(json.dumps(page.ast.to_json())))
            if out_path.name != "index.html" and (self.output_dir / out_path.parent / "index.html").exists():
                ast.metadata["report-url"] = "index.html"
            post_to_html(
                ast,
                root_of(out_path),
                page.lang,
                profile,
                self.output_dir / out_path,
                self,
                # its own years; a page without dates gets the site's only in a full build
                years=format_years(page.years),
                per_profile=page.per_profile,
            )
        time_elapse.report(f"{page.path} redone.")

    def live_routine(
        self,
        pages: list[Page] = [],
    ) -> None:
        """Routines near the end of going live."""
        if self.serve:
            if (url := self.serve_open) is not None:
                self.open_browser(url)
            if self.watch and self.watch_open:
                for page in pages:
                    self.open_browser(page.url)
        if self.watch and self.watch_code:
            for page in pages:
                code(self.output_dir / page.out_path)

    def pages_to_be_watched(
        self,
        all_pages: Sequence[Page],
    ) -> list[Page]:
        """Watch and re-render pages."""
        globs = self.watch
        time_elapse = TimeElapse(logger)

        cur_dir = Path(".")
        paths = list(chain.from_iterable(cur_dir.glob(glob) for glob in globs))
        time_elapse.report(f"Found {len(paths)} paths to watch.")
        logger.debug("Watching the following paths: %s", paths)

        lut = {page.path: page for page in all_pages}
        try:
            pages = [lut[path] for path in paths]
        except KeyError as e:
            raise ValueError(
                f"Cannot find page/post with path from the following KeyError: {e}"
            )
        time_elapse.report(f"Found pages to match.")
        return pages

    def observe_pages_with_watchdog(
        self,
        pages: List[Page],
    ) -> None:
        """Watch using watchdog which is observer based.

        Currently this is almost feature parity with :py:func:`observe_pages_with_livereload`.

        livereload is polling-based (except on Linux with a special call method not implemented here.)
        Here, the way we reload the page is by calling `open_browser` on the modified page.
        This has the side-effect of the browser windows popping up from backgrounds.
        """
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        if TYPE_CHECKING:
            from watchdog.events import FileSystemEvent

        class PageEventHandler(FileSystemEventHandler):
            def __init__(
                self,
                config: Config,
                pages: dict[str, Page],
                modules: dict[str, ModuleType],
            ):
                self.config = config
                self.pages = pages
                self.modules = modules

            def on_modified(self, event: FileSystemEvent) -> None:
                config = self.config
                pages = self.pages
                modules = self.modules
                path = event.src_path
                logger.info("%s %s. Updating...", path, event.event_type)
                if path in pages:
                    page = pages[path]
                    config.make_page(page)
                    if config.serve and config.watch_open:
                        config.open_browser(page.url)
                elif path in modules:
                    module = modules[path]
                    logger.info("Reloading module %s", module)
                    try:
                        reload(module)
                    except Exception as e:
                        logger.warning(
                            "Exception encoutnered when reloading module %s: %s",
                            module,
                            e,
                        )
                else:
                    logger.warning("Don't know how to update %s", path)

        event_handler = PageEventHandler(
            self, path_to_page(pages), self.modules_to_be_watched
        )
        observer = Observer()
        for page in pages:
            path = page.path
            observer.schedule(event_handler, path, recursive=True)
            logger.info("Watching page %s", path)
        for module_path in self.modules_to_be_watched:
            observer.schedule(event_handler, module_path, recursive=True)
            logger.info("Watching module %s", module_path)

        logger.info("Observing using watchdog...")
        observer.start()
        self.live_routine(pages)
        if self.serve:
            httpd = self.serving
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                logger.info("Shutting down Watchdog & ThreadingHTTPServer")
                observer.stop()
                httpd.shutdown()
                logger.info("Shutted down Watchdog & ThreadingHTTPServer")
            finally:
                logger.info("Joining observer")
                observer.join()
                logger.info("Joint observer")
        else:
            try:
                while True:
                    # just some long running command to be KeyboardInterrupted
                    time.sleep(86400)
            except KeyboardInterrupt:
                logger.info("Shutting down Watchdog")
                observer.stop()
                logger.info("Shutted down Watchdog")
            finally:
                logger.info("Joining observer")
                observer.join()
                logger.info("Joint observer")

    def observe_pages_with_livereload(
        self,
        pages: List[Page],
    ) -> None:
        """Watch using livereload which is polling based."""
        from livereload import Server

        if not self.serve:
            logger.warning("livereload must serve.")
            self.serve = True

        server = Server()
        for page in pages:
            path = page.path
            server.watch(str(path), partial(self.make_page, page))
            logger.info("Watching page %s", path)
        for module_path, module in self.modules_to_be_watched.items():
            server.watch(module_path, partial(reload, module))
            logger.info("Watching module %s", module_path)

        logger.info("Observing using livereload...")
        self.live_routine(pages)
        server.serve(root=str(self.output_dir), port=self.serve_port)

    def live(
        self,
        all_pages: Sequence[Page],
    ) -> None:
        """Go live."""
        # let watch_pages handle serve cases
        if self.watch:
            pages = self.pages_to_be_watched(all_pages)
            if (watch_with := self.watch_with) == "livereload":
                self.observe_pages_with_livereload(pages)
            elif watch_with == "watchdog":
                self.observe_pages_with_watchdog(pages)
            else:
                raise ValueError(watch_with)
        # only serve ourselves if not watching
        elif self.serve:
            httpd = self.serving
            self.live_routine()
            try:
                httpd.serve_forever()
                logger.info("Served.")
            except KeyboardInterrupt:
                logger.info("Shutting down ThreadingHTTPServer")
                httpd.shutdown()
                logger.info("Shutted down ThreadingHTTPServer")
