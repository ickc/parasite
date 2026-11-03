"""output-file, format-links and image-alt, in a site built end to end."""

from __future__ import annotations

import pytest

from para.settings import load

CONFIG = """
[site]
url = "https://example.org/"
title = "T"
[files]
[search]
enabled = false
[check]
links = false
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "parasite.toml", CONFIG)
    write(tmp_path / "media/a.png", "")
    return tmp_path


def build(site):
    load(site / "parasite.toml")().exec()
    return site / "output"


def test_output_file_and_format_links(site):
    write(
        site / "posts/a.md",
        "---\ntitle: A\ndate: 2020-01-01\nimage: media/a.png\nimage-alt: A plot\n"
        "format:\n  html:\n    output-file: page.html\n  slides:\n    output-file: talk.html\n"
        "format-links: [slides]\n---\n\n# One\n\nText.\n",
    )
    write(site / "posts/b.md", "---\ntitle: B\ndate: 2020-01-02\nformat: [html, slides]\nformat-links: false\n---\n\n# One\n")
    write(site / "posts/c.md", "---\ntitle: C\ndate: 2020-01-03\nformat: [html, slides]\n---\n\n# One\n")
    out = build(site)
    page, talk = (out / "a/page.html").read_text(), (out / "a/talk.html").read_text()
    # the page links to its slides, as format-links says; the slides to nothing
    assert '<a href="talk.html">Slides</a>' in page
    assert ">Report</a>" not in talk
    # false: none, not even slidy's Report; unset: as before
    assert ">Report</a>" not in (out / "b/present.html").read_text()
    assert '<a href="index.html">Report</a>' in (out / "c/present.html").read_text()
    assert "output-links" not in (out / "c/index.html").read_text()
    # listings link to the page by its file, and its image's text
    index = (out / "index.html").read_text()
    assert 'href="./a/page.html"' in index and 'alt="A plot"' in index


def test_output_file_is_a_file_name(site):
    write(site / "posts/a.md", "---\ntitle: A\ndate: 2020-01-01\noutput-file: ../x.html\n---\n\nText.\n")
    with pytest.raises(ValueError, match="output-file"):
        build(site)
