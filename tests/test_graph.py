from __future__ import annotations

from pathlib import Path

import panflute as pf
import pytest

from para.data import Page, Post
from para.record import Record

from conftest import make_page

pytest.importorskip("paragraphic")
from para.graph import records  # noqa: E402


def page(cls: type[Page], path: str, ast: pf.Doc, format: tuple[str, ...] = ("html",)) -> Page:
    return make_page(cls, path, ast, format)


def test_records():
    a = page(
        Post,
        "x/a.md",
        pf.Doc(
            pf.Para(pf.Link(pf.Str("b"), url="../b/"), pf.Link(pf.Str("out"), url="https://example.org/p#s")),
            pf.Div(
                pf.Div(pf.Para(pf.Link(pf.Str("doi"), url="https://doi.org/10/x")), identifier="ref-key2020"),
                identifier="refs",
            ),
            metadata={"title": "A", "date": "2020-01-01", "tags": ["T"]},
        ),
    )
    b = page(Post, "x/b.md", pf.Doc(metadata={"title": "B", "date": "2020-01-02"}))
    slides = page(Page, "x/a.markdown", pf.Doc(metadata={"title": "A slides"}), ("slides",))
    pages = [Record.from_page(p, isinstance(p, Post)) for p in (a, b, slides)]
    res = records(pages, {"x/a/index.html", "x/b/index.html"}, None)
    ra = res["x/a/index.html"]
    assert ra.has_content and not res["x/a/present.html"].has_content
    assert ra.links == ["x/b/index.html"]
    assert ra.external == ["https://example.org/p"]
    assert ra.citations == ["key2020"]
    assert ra.cited_urls == {"key2020": ["https://doi.org/10/x"]}
    assert ra.alternates == ["x/a/present.html"]
    assert ra.categories == ["T"]
