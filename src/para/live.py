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
from typing import TYPE_CHECKING, ClassVar, List, Optional


import panflute as pf

from .apps import post_to_html, post_to_pdf, read_md_to_ast
from .data import format_years, root_of
from .config import Config as StaticConfig
from .util import TimeElapse, inherit_args

if TYPE_CHECKING:
    from http.server import ThreadingHTTPServer
    from types import ModuleType
    from typing import Sequence

    from .config import Profile
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


RELOAD_URL = "/__para_reload"
# polls the rebuild counter, reloading the page when it changes
RELOAD_SCRIPT = (
    "<script>(() => { let seen; setInterval(async () => { try {"
    f" const now = await (await fetch('{RELOAD_URL}')).text();"
    " if (seen !== undefined && now !== seen) location.reload(); seen = now;"
    " } catch (e) {} }, 1000); })();</script>"
).encode()


def reloading_handler(config: Optional[Config]) -> type:
    """A static file handler; with ``config`` (watching), HTML pages are served with
    :data:`RELOAD_SCRIPT` and :data:`RELOAD_URL` answers the rebuild counter."""
    from http.server import SimpleHTTPRequestHandler

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if config is None:
                return super().do_GET()
            if self.path == RELOAD_URL:
                return self._send(str(config._generation).encode(), "text/plain")
            path = Path(self.translate_path(self.path))
            if self.path.split("?")[0].endswith("/"):
                path = path / "index.html"
            if path.suffix != ".html" or not path.is_file():
                return super().do_GET()
            html = path.read_bytes()
            end = html.rfind(b"</body>")
            html = html + RELOAD_SCRIPT if end < 0 else html[:end] + RELOAD_SCRIPT + html[end:]
            self._send(html, "text/html; charset=utf-8")

        def _send(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def path_to_page(pages: list[Page]) -> dict[str, Page]:
    return {str(page.path.absolute()): page for page in pages}


@inherit_args
@dataclass
class Config(StaticConfig):
    """Configure live serving parameters.

    Args:
        watch: glob patterns of source files to be watched (relative to current directory)
        watch_open: if specified, open all pages that are currently watching.
        watch_code: if specified, open all sources that are currently watching in VSCode.
        watch_module: if specified, watch & reload this module.
        serve: if specified, open a server and serve indefinitely; pages served while watching reload when rebuilt.
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
    serve_open: Optional[str] = None

    # bumped after each rebuild while watching: served pages poll it and reload
    _generation: ClassVar[int] = 0

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

        from http.server import ThreadingHTTPServer

        httpd = ThreadingHTTPServer(
            (host, port),
            partial(reloading_handler(self if self.watch else None), directory=directory),
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
        from .site import page_options

        time_elapse = TimeElapse(logger)

        def read(select: Profile | None) -> pf.Doc:
            with page_options(page) as extra:
                return read_md_to_ast(
                    self.pandoc_input_options,
                    self.filters,
                    inputs=[page.path],
                    **self.media_options(page),
                    select=select,
                    extra_options=extra,
                    conversion=page.convert,
                )

        page.ast = read(page.profiles[0] if page.per_profile else None)
        page.set_profiles()
        outputs = page.outputs
        for i, (profile, out_path) in enumerate(outputs):
            if page.per_profile:
                ast = page.ast if i == 0 else read(profile)
            else:
                ast = page.ast if i == len(outputs) - 1 else pf.load(io.StringIO(json.dumps(page.ast.to_json())))
            if out_path.name != "index.html" and (self.output_dir / out_path.parent / "index.html").exists():
                ast.metadata["report-url"] = "index.html"
            if profile.to == "pdf":
                updated = page.record.updated if page.record is not None else None
                post_to_pdf(ast, profile, self.output_dir / out_path, self, epoch=0 if updated is None else int(updated.timestamp()))
                continue
            post_to_html(
                ast,
                root_of(out_path),
                page.lang,
                profile,
                self.output_dir / out_path,
                self,
                # its own years; a page without dates gets the site's only in a full build
                years=format_years(page.years),
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
        time_elapse.report("Found pages to match.")
        return pages

    def observe_pages_with_watchdog(
        self,
        pages: List[Page],
    ) -> None:
        """Watch ``pages`` (and the modules to reload) with watchdog, rebuilding a page when
        its source changes; served pages reload themselves (see :func:`reloading_handler`)."""
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
                    type(config)._generation += 1
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

    def live(
        self,
        all_pages: Sequence[Page],
    ) -> None:
        """Go live."""
        # let watch_pages handle serve cases
        if self.watch:
            pages = self.pages_to_be_watched(all_pages)
            self.observe_pages_with_watchdog(pages)
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
