"""Search: a Pagefind index of the pages' records, and the search page.

Pagefind (an optional dependency, ``pagefind[bin]``) shards its index by term and its
documents by content, so one more page changes a few files. It indexes the records
(their URL, title and text, see :mod:`para.record`), not the rendered HTML, and
its files are written through the output tree: those whose bytes did not change are
not rewritten.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import Sequence

    from .output import Output
    from .record import Record

logger = getLogger(__name__)

BUNDLE = "pagefind"


def _language(lang: str) -> str:
    """Pagefind's language code: ``zh_tw`` is ``zh-tw``."""
    return lang.replace("_", "-").lower()


async def _index(records: Sequence[Record], out: Path) -> None:
    from pagefind.index import IndexConfig, PagefindIndex

    async with PagefindIndex(IndexConfig(write_playground=False)) as index:
        for record in records:
            await index.add_custom_record(
                url="/" + record.url,
                content=record.text,
                language=_language(record.lang),
                meta={"title": record.title or record.url},
                # no filters (tags as facets): Pagefind 1.5.2 writes them differently
                # from one run to the next, so its files would change every build
            )
        await index.write_files(output_path=str(out))


def write_pagefind(records: Sequence[Record], output_dir: Path, output: Output) -> None:
    """Pagefind's index of ``records`` and its UI, at ``output_dir``/pagefind/."""
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(_index(records, Path(tmp)))
        files = sorted(p for p in Path(tmp).rglob("*") if p.is_file())
        for path in files:
            data = path.read_bytes()
            if path.name == "pagefind-entry.json":
                # its languages in a stable order (Pagefind's varies from run to run)
                entry = json.loads(data)
                entry["languages"] = dict(sorted(entry["languages"].items()))
                data = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            output.write(output_dir / BUNDLE / path.relative_to(tmp), data, "search")
    logger.info("search: %s pages, %s files", len(records), len(files))


def search_page_ast(root: str, lang: str = "en") -> pf.Doc:
    """The search page: Pagefind's UI, searching for ``?q=`` on arrival. Results link
    relative to the page, so the site works under any path."""
    return pf.Doc(
        pf.RawBlock('<div id="search"></div>', format="html"),
        metadata={
            "title": "Search",
            "lang": lang,
            "header-includes": pf.MetaBlocks(
                pf.RawBlock(f'<link rel="stylesheet" href="{root}/{BUNDLE}/pagefind-ui.css" />', format="html")
            ),
            "include-after": pf.MetaBlocks(
                pf.RawBlock(
                    f'<script src="{root}/{BUNDLE}/pagefind-ui.js"></script>\n'
                    "<script>\n"
                    "window.addEventListener('DOMContentLoaded', function () {\n"
                    # Pagefind resolves a relative bundlePath against its own script
                    f"  var bundle = new URL('{root}/{BUNDLE}/', document.baseURI).href;\n"
                    "  var ui = new PagefindUI({element: '#search', bundlePath: bundle, showImages: false,\n"
                    f"    processResult: function (result) {{ result.url = '{root}' + result.url; return result; }}}});\n"
                    "  var q = new URLSearchParams(window.location.search).get('q');\n"
                    "  if (q) { ui.triggerSearch(q); }\n"
                    "});\n"
                    "</script>",
                    format="html",
                )
            ),
        },
    )
