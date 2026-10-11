"""A site with translations, built end to end (see para.lang)."""

from __future__ import annotations

import pytest

from para.settings import load

pytest.importorskip("opencc")

CONFIG = """
[site]
url = "https://example.org/"
title = { zh-Hant = "祺", en = "KcIc" }
lang = "zh-Hant"
[translations.en]
[translations.zh-Hans]
convert = "hk2s"
[files]
[search]
enabled = false
[check]
links = false
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_translations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "parasite.toml", CONFIG)
    write(tmp_path / "posts/a.md", "---\ntitle: 簡易食譜\ndate: 2020-01-01\ntags: [simple]\n---\n\n標籤 [b](../b/)\n")
    # its own title; the date and tags are a.md's
    write(tmp_path / "posts/a.en.md", "---\ntitle: Simple recipe\n---\n\nTags\n")
    write(tmp_path / "posts/b.md", "---\ntitle: 乙\ndate: 2020-01-02\nlang: en\n---\n\nEnglish only\n")
    load(tmp_path / "parasite.toml")().exec()
    out = tmp_path / "output"
    a = (out / "a/index.html").read_text()
    en = (out / "a/index.en.html").read_text()
    hans = (out / "a/index.zh-hans.html").read_text()
    # the primary, its translation by hand, and the one OpenCC made
    assert 'lang="zh-Hant"' in a and "簡易食譜" in a
    assert 'lang="en"' in en and "Simple recipe" in en and "2020-01-01" in en
    assert 'lang="zh-Hans"' in hans and "简易食谱" in hans and "标签" in hans
    # they link to each other, beside each other; links between pages work as written
    for html in (a, en, hans):
        assert 'hreflang="en"' in html and 'hreflang="zh-Hans"' in html and 'hreflang="zh-Hant"' in html
    assert 'href="index.en.html"' in a and 'href="./"' in en and 'href="index.zh-hans.html"' in en
    assert 'href="../b/"' in hans
    # a page in English only is not converted; listings show each page once
    assert not (out / "b/index.zh-hans.html").exists()
    index = (out / "index.html").read_text()
    assert index.count("a/index.") == 0 and "index.en.html" not in index
    tags = (out / "tags/simple/index.html").read_text()
    assert "簡易食譜" in tags and "Simple recipe" not in tags and "简易食谱" not in tags
