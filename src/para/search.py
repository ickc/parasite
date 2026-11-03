"""Search: a Pagefind index of the pages' records, and the search page.

Pagefind (an optional dependency, ``pagefind[bin]``) shards its index by term and its
documents by content, so one more page changes a few files. It indexes the records
(their URL, title and text, see :mod:`para.record`), not the rendered HTML, and
its files are written through the output tree: those whose bytes did not change are
not rewritten.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import tempfile
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import panflute as pf

if TYPE_CHECKING:
    from typing import Any, Sequence

    from .output import Output
    from .record import Record

logger = getLogger(__name__)

BUNDLE = "pagefind"


def _language(lang: str) -> str:
    """Pagefind's language code: ``zh_tw`` is ``zh-tw``."""
    return lang.replace("_", "-").lower()


async def _index(records: Sequence[Record], out: Path, language: str) -> None:
    from pagefind.index import IndexConfig, PagefindIndex

    # leaving the context writes the files, to the output path of the config
    async with PagefindIndex(IndexConfig(write_playground=False, output_path=str(out))) as index:
        for record in records:
            filters = {"tag": sorted(record.tags)} if record.tags else {}
            if record.category:
                filters["category"] = [record.category]
            await index.add_custom_record(
                url="/" + record.url,
                # the tags are searched too, as words of the page
                content="\n\n".join((record.text, " ".join(record.tags))) if record.tags else record.text,
                # one index for the site: Pagefind searches only the index of the search
                # page's language, so pages in another (kcic's English posts) would not
                # be found
                language=language,
                meta={"title": record.title or record.url},
                filters=filters,
            )


# Pagefind's files: gzipped, a signature, then CBOR (definite lengths, smallest heads)

SIGNATURE = b"pagefind_dcd"


def _cbor_load(data: bytes, i: int = 0) -> tuple[Any, int]:
    major, info = data[i] >> 5, data[i] & 31
    i += 1
    if info < 24:
        n = info
    elif info < 28:
        size = 1 << (info - 24)
        n = int.from_bytes(data[i : i + size], "big")
        i += size
    else:
        raise ValueError(f"CBOR: not read here, {data[i - 1]:#x}")
    if major == 0:
        return n, i
    if major == 2:
        return bytes(data[i : i + n]), i + n
    if major == 3:
        return data[i : i + n].decode("utf-8"), i + n
    if major == 4:
        res = []
        for _ in range(n):
            item, i = _cbor_load(data, i)
            res.append(item)
        return res, i
    raise ValueError(f"CBOR: major type {major} not read here")


def _cbor_dump(value: Any) -> bytes:
    if isinstance(value, int):
        major, n, body = 0, value, b""
    elif isinstance(value, bytes):
        major, n, body = 2, len(value), value
    elif isinstance(value, str):
        body = value.encode("utf-8")
        major, n = 3, len(body)
    else:
        major, n = 4, len(value)
        body = b"".join(_cbor_dump(item) for item in value)
    if n < 24:
        head = bytes([major << 5 | n])
    else:
        info = next(info for info in range(24, 28) if n < 1 << (8 << (info - 24)))
        head = bytes([major << 5 | info]) + n.to_bytes(1 << (info - 24), "big")
    return head + body


def _read(data: bytes) -> Any:
    raw = gzip.decompress(data)
    if not raw.startswith(SIGNATURE):
        raise ValueError("not a Pagefind file")
    value, end = _cbor_load(raw, len(SIGNATURE))
    # what is read here is written back the same: else it is not this format
    if end != len(raw) or _cbor_dump(value) != raw[len(SIGNATURE) :]:
        raise ValueError("not read whole")
    return value


def _write(value: Any) -> bytes:
    return gzip.compress(SIGNATURE + _cbor_dump(value), mtime=0)


def _named(language: str, data: bytes, length: int) -> str:
    return f"{language}_{hashlib.sha256(data).hexdigest()[:length]}"


def _stable(files: dict[str, bytes]) -> dict[str, bytes]:
    """Pagefind's files with their filters (tags) in a stable order.

    Pagefind 1.5 writes a filter's values in an order that varies from run to run (a
    hash map's), so its filter file, and the language's meta file naming it, would
    change every build. Here the values are sorted, and the two files renamed by their
    new content, as Pagefind names them.
    """
    entry = json.loads(files["pagefind-entry.json"])
    for language, info in entry["languages"].items():
        meta_path = f"pagefind.{info['hash']}.pf_meta"
        meta = _read(files.pop(meta_path))
        filters = meta[3]
        for item in filters:
            name, digest = item
            path = f"filter/{digest}.pf_filter"
            values = _read(files.pop(path))
            values[1].sort(key=lambda value: value[0])
            data = _write(values)
            item[1] = _named(language, data, 7)
            files[f"filter/{item[1]}.pf_filter"] = data
        filters.sort(key=lambda item: item[0])
        data = _write(meta)
        info["hash"] = _named(language, data, 10)
        files[f"pagefind.{info['hash']}.pf_meta"] = data
    # its languages in a stable order too
    entry["languages"] = dict(sorted(entry["languages"].items()))
    files["pagefind-entry.json"] = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return files


def write_pagefind(records: Sequence[Record], output_dir: Path, output: Output, lang: str = "en") -> None:
    """Pagefind's index of ``records`` and its UI, at ``output_dir``/pagefind/, in the
    site's language ``lang``, that of the search page."""
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(_index(records, Path(tmp), _language(lang)))
        files = {p.relative_to(tmp).as_posix(): p.read_bytes() for p in sorted(Path(tmp).rglob("*")) if p.is_file()}
    files = _stable(files)
    for path, data in sorted(files.items()):
        output.write(output_dir / BUNDLE / path, data, "search")
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
