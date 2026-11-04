"""URLs in a page, rebased to work from the page's output directory."""

from pathlib import Path

import panflute as pf

from para.media import relative_root_urls


def urls(markdown: str, out_dir: str) -> list[str]:
    doc = pf.convert_text(markdown, standalone=True)
    doc = relative_root_urls(doc, Path("output") / out_dir, Path("output"))
    found = []
    doc.walk(lambda e, d: found.append(e.url) if isinstance(e, (pf.Link, pf.Image)) else None)
    return found


def test_urls_from_the_root_are_relative_to_the_page():
    """A site works under any path: /about/ from journal/x/ is ../../about/."""
    md = "[a](/about/) [b](/rss.xml) [c](/) [d](/journal/y/#top) [e](//cdn.example/x.js) [f](https://example.org/a)"
    assert urls(md, "journal/x") == ["../../about/", "../../rss.xml", "../../", "../y/#top", "//cdn.example/x.js", "https://example.org/a"]
    assert urls("[a](/about/) [c](/) [r](/rss.xml)", "") == ["about/", "./", "rss.xml"]
