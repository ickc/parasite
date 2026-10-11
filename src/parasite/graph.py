"""The post graph, from the documents rather than the rendered HTML.

sitegraph (an optional dependency) reads a rendered site's HTML, so that it works for any
generator. parasite has the documents already, so it gives sitegraph its page records
directly: links, citations and external links from the document, the nodes from what is
listed (posts that are not drafts), and a page's other outputs (its slides) as alternates
that stand for it. Nothing is read back.
"""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import Sequence

    from .data import Page

logger = getLogger(__name__)

VIEWER = ("sitegraph.js", "sitegraph-local.js", "sitegraph.css")


def _bibliography(doc: pf.Doc) -> list[pf.Div]:
    """citeproc's entries: the divs with id ref-<key> inside #refs."""
    found: list[pf.Div] = []

    def action(elem: pf.Element, doc: pf.Doc) -> None:
        if isinstance(elem, pf.Div) and elem.identifier.startswith("ref-"):
            found.append(elem)

    doc.walk(action)
    return found


def _link_elements(elem: pf.Element) -> list[pf.Link]:
    found: list[pf.Link] = []

    def action(e: pf.Element, doc: pf.Doc) -> None:
        if isinstance(e, pf.Link):
            found.append(e)

    elem.walk(action)
    return found


def _links(elem: pf.Element) -> list[str]:
    return [link.url for link in _link_elements(elem)]


def records(pages: Sequence[Page], listed: set[str], site_url: str | None):
    """sitegraph Page records, by output path, for ``pages``; nodes are those in
    ``listed`` (output paths)."""
    from sitegraph.extract import Page as GraphPage
    from sitegraph.extract import Resolver

    resolve = Resolver(site_url)
    out_paths = {page.out_path.as_posix() for page in pages}
    by_dir: dict[str, list[str]] = {}
    for path in sorted(out_paths):
        by_dir.setdefault(path.rsplit("/", 1)[0] if "/" in path else "", []).append(path)

    res = {}
    for page in pages:
        path = page.out_path.as_posix()
        doc = page.ast
        entries = _bibliography(doc)
        in_bibliography = {id(link) for entry in entries for link in _link_elements(entry)}
        record = GraphPage(path=path)
        record.has_content = path in listed
        record.title = page.title or ""
        record.date = str(doc.get_metadata("date", "") or "")
        record.categories = list(page.tags)
        record.links = [t for url in _links(doc) if (t := resolve(path, url))]
        record.external = sorted(
            {u for link in _link_elements(doc) if id(link) not in in_bibliography and (u := resolve.external(link.url))}
        )
        record.cited_urls = {
            entry.identifier.removeprefix("ref-"): sorted({u for url in _links(entry) if (u := resolve.external(url))})
            for entry in entries
        }
        record.citations = sorted(record.cited_urls)
        # the page's other outputs in its directory (slides beside a page)
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        record.alternates = [p for p in by_dir.get(directory, []) if p != path]
        res[path] = record
    return res


def write_graph(
    pages: Sequence[Page],
    listed: set[str],
    output_dir: Path,
    site_url: str | None = None,
    uncoloured: Sequence[str] = (),
    colours: int = 7,
) -> None:
    """Write graph.json and sitegraph's viewer into ``output_dir``."""
    from sitegraph.extract import Config, build_graph

    config = Config(output_dir=output_dir, site_url=site_url, uncoloured=list(uncoloured), colours=colours)
    graph = build_graph(config, records(pages, listed, site_url))
    (output_dir / "graph.json").write_text(json.dumps(graph, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    viewer = files("sitegraph") / "viewer"
    for name in VIEWER:
        with (viewer / name).open("rb") as src, open(output_dir / name, "wb") as dst:
            shutil.copyfileobj(src, dst)
    logger.info("graph: %s pages, %s links", len(graph["nodes"]), len(graph["links"]))
