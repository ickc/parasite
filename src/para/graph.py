"""The post graph, from the documents rather than the rendered HTML.

sitegraph (an optional dependency) reads a rendered site's HTML, so that it works for any
generator. parasite has the pages' records already (see :mod:`para.record`), made from
the documents as read, so it gives sitegraph its page records directly: links,
citations and external links, the nodes from what is listed (posts that are not
drafts), and a page's other outputs (its slides) as alternates that stand for it.
Nothing is read back.
"""

from __future__ import annotations

import json
from importlib.resources import files
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import Sequence

    from .output import Output
    from .record import Record

logger = getLogger(__name__)

VIEWER = ("sitegraph.js", "sitegraph-local.js", "sitegraph.css")


class Recorder:
    """Makes sitegraph Page records from page records; nodes are the output paths in
    ``listed``."""

    def __init__(self, pages: Sequence[Record], listed: set[str], site_url: str | None) -> None:
        from sitegraph.extract import Resolver

        self.resolve = Resolver(site_url)
        self.listed = listed
        # a page's other outputs in its directory (slides beside a page)
        self.by_dir: dict[str, list[str]] = {}
        for path in sorted({page.out_path for page in pages}):
            self.by_dir.setdefault(path.rsplit("/", 1)[0] if "/" in path else "", []).append(path)

    def __call__(self, page: Record):
        from sitegraph.extract import Page as GraphPage

        resolve = self.resolve
        path = page.out_path
        record = GraphPage(path=path)
        record.has_content = path in self.listed
        record.title = page.title or ""
        record.date = page.date or ""
        record.categories = list(page.tags)
        record.links = [t for url in page.links if (t := resolve(path, url))]
        record.external = sorted({u for url in page.external_candidates if (u := resolve.external(url))})
        record.cited_urls = {
            key: sorted({u for url in urls if (u := resolve.external(url))}) for key, urls in page.citations.items()
        }
        record.citations = sorted(record.cited_urls)
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        record.alternates = [p for p in self.by_dir.get(directory, []) if p != path]
        return record


def records(pages: Sequence[Record], listed: set[str], site_url: str | None):
    """sitegraph Page records, by output path, for ``pages``."""
    recorder = Recorder(pages, listed, site_url)
    return {page.out_path: recorder(page) for page in pages}


def graph_page_ast(lang: str = "en") -> pf.Doc:
    """/graph/: the whole post graph."""
    return pf.Doc(
        pf.RawBlock('<div class="sitegraph" data-src="../graph.json"></div>', format="html"),
        metadata={
            "title": "Graph",
            "lang": lang,
            "include-after": pf.MetaBlocks(
                pf.RawBlock(
                    '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
                    '<script src="../sitegraph.js"></script>',
                    format="html",
                )
            ),
        },
    )


def write_graph(
    records: dict,
    output_dir: Path,
    site_url: str | None = None,
    uncoloured: Sequence[str] = (),
    colours: int = 7,
    output: Output | None = None,
) -> None:
    """Write graph.json from ``records`` (by output path), and sitegraph's viewer, into
    ``output_dir``."""
    from sitegraph.extract import Config, build_graph

    config = Config(output_dir=output_dir, site_url=site_url, uncoloured=list(uncoloured), colours=colours)
    graph = build_graph(config, records)
    data = {"graph.json": (json.dumps(graph, indent=1, ensure_ascii=False) + "\n").encode("utf-8")}
    viewer = files("sitegraph") / "viewer"
    for name in VIEWER:
        data[name] = (viewer / name).read_bytes()
    for name, content in data.items():
        if output is None:
            (output_dir / name).write_bytes(content)
        else:
            output.write(output_dir / name, content, "graph")
    logger.info("graph: %s pages, %s links", len(graph["nodes"]), len(graph["links"]))
