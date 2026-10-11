from __future__ import annotations

import pytest

from para.settings import SettingsError, load, merge, read


def test_merge_tables_key_by_key_lists_whole():
    base = {"site": {"url": "a", "lang": "en"}, "files": {"files": "", "media": "media"}, "x": [1, 2]}
    over = {"site": {"url": "b"}, "files": {"media": "m"}, "x": [3]}
    assert merge(base, over) == {"site": {"url": "b", "lang": "en"}, "files": {"media": "m"}, "x": [3]}


def test_a_sites_filters_come_first_in_its_order():
    base = {"filters": {"a": {"default": True}, "b": {}}}
    over = {"filters": {"c": {}, "a": {"default": False}}}
    assert list(merge(base, over)["filters"]) == ["c", "a", "b"]
    assert merge(base, over)["filters"]["a"] == {"default": False}


def write(tmp_path, text):
    path = tmp_path / "parasite.toml"
    path.write_text(text)
    return path


def test_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write(
        tmp_path,
        """
[site]
title = { en = "T", zh_tw = "祺" }
author = "A"
email = "a@b"
[profiles.html]
footer = '© {years} <a href="mailto:{email}">{author}</a> function f(){ return 1; }'
""",
    )
    config = load(path)()
    # keys by language are BCP 47 tags (para.lang)
    assert config.blog_title == {"en": "T", "zh-TW": "祺"}
    assert config.blog_author == {"en": "A"}
    html, slides = config.profiles["html"], config.profiles["slides"]
    footer = config.part(html, "footer", "en").replace("{years}", "2020")
    assert footer == '© 2020 <a href="mailto:a@b">A</a> function f(){ return 1; }'
    assert config.part(slides, "footer", "en") == ""
    assert slides.options[-1] == "--to=slidy"
    assert [f.__name__ for f in html.filters] == ["lightgallery_filter", "mathjax_bold_ell_filter"]
    assert read(path)["site"]["lang"] == "en"


def test_unknown_profile(tmp_path):
    path = write(tmp_path, '[[sources]]\ndir = "posts"\next = [".md"]\nformat = ["nope"]\n')
    with pytest.raises(SettingsError):
        load(path)().collections


def test_math_method(monkeypatch):
    from para import config

    monkeypatch.setattr(config, "pandoc_version", lambda: (3, 12))
    assert config.math_method(("--mathjax", "--wrap=none", "--katex=https://k/")) == (
        "--math-method=mathjax",
        "--wrap=none",
        "--math-method=katex:https://k/",
    )
    monkeypatch.setattr(config, "pandoc_version", lambda: (3, 1, 1))
    assert config.math_method(("--mathjax",)) == ("--mathjax",)
